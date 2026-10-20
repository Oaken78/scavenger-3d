shader_type spatial;
// Ground of the street: cracked, damp asphalt on the road strip, moss and grass elsewhere.
// Everything is procedural in world space (x, z metres), so the plane can be any size.

// Road centre line start, world (x, z) metres (from layout.json "road").
uniform vec2 road_from = vec2(-20.0, 0.0);
// Road centre line end, world (x, z) metres.
uniform vec2 road_to = vec2(20.0, 0.0);
// Half the road width in metres.
uniform float road_half_width = 4.0;
// Asphalt base colour (linear-ish albedo).
uniform vec3 asphalt_color : source_color = vec3(0.09, 0.09, 0.1);
// Colour inside the cracks (darker, mossy).
uniform vec3 crack_color : source_color = vec3(0.03, 0.05, 0.03);
// Moss and grass colours, mixed by noise.
uniform vec3 moss_color : source_color = vec3(0.08, 0.14, 0.05);
uniform vec3 grass_color : source_color = vec3(0.14, 0.18, 0.07);
// Bare dirt patches in the grass.
uniform vec3 dirt_color : source_color = vec3(0.12, 0.1, 0.07);
// Faded lane paint on the centre line.
uniform vec3 paint_color : source_color = vec3(0.5, 0.48, 0.38);
// Asphalt roughness when dry and in puddles (lower = wetter, sharper light pools).
uniform float road_roughness : hint_range(0.0, 1.0) = 0.55;
uniform float puddle_roughness : hint_range(0.0, 1.0) = 0.08;
// Share of the road covered by puddles (0..1).
uniform float puddle_amount : hint_range(0.0, 1.0) = 0.35;
// Crack density: larger = more, finer cracks.
uniform float crack_scale = 0.9;
// Softness of the road edge where moss creeps over, metres.
uniform float edge_soft = 1.2;

// A hole in the ground (world x, z rectangle) where the subway stairs go down; off when hole_enabled is false.
uniform bool hole_enabled = false;
uniform vec2 hole_min = vec2(0.0);
uniform vec2 hole_max = vec2(0.0);

varying vec3 world_pos;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
		mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.5;
	for (int k = 0; k < 4; k++) {
		v += a * vnoise(p);
		p *= 2.03;
		a *= 0.5;
	}
	return v;
}

// Cellular edge distance: small near cell borders, which reads as a crack network.
float cracks(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float d1 = 8.0;
	float d2 = 8.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = vec2(hash(i + g), hash(i + g + 17.0));
			float d = length(g + o - f);
			if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
		}
	}
	return d2 - d1;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	if (hole_enabled && all(greaterThan(p, hole_min)) && all(lessThan(p, hole_max))) {
		discard;
	}
	// Distance to the road centre segment.
	vec2 ab = road_to - road_from;
	float t = clamp(dot(p - road_from, ab) / dot(ab, ab), 0.0, 1.0);
	vec2 closest = road_from + ab * t;
	float dist = length(p - closest);
	float edge_noise = (fbm(p * 0.6) - 0.5) * 2.0 * edge_soft;
	float road = 1.0 - smoothstep(road_half_width - edge_soft * 0.3, road_half_width + 0.2, dist + edge_noise);

	// Asphalt: grain, cracks, puddles, faded centre paint.
	float grain = fbm(p * 3.0);
	float c = cracks(p * crack_scale + fbm(p * 1.5) * 0.6);
	float crack = 1.0 - smoothstep(0.02, 0.07, c);
	float puddle = smoothstep(1.0 - puddle_amount, 1.0 - puddle_amount + 0.08, fbm(p * 0.35 + 3.1));
	vec3 asphalt = asphalt_color * (0.75 + grain * 0.5);
	float dash = step(0.5, fract(dot(p - road_from, normalize(ab)) / 3.0)) * (1.0 - smoothstep(0.08, 0.14, dist));
	asphalt = mix(asphalt, paint_color * (0.6 + grain * 0.4), dash * 0.6 * step(fbm(p * 2.0), 0.6));
	asphalt = mix(asphalt, crack_color, crack);
	asphalt *= mix(1.0, 0.55, puddle);

	// Ground: moss and grass patches, some dirt.
	float n = fbm(p * 0.45);
	vec3 ground = mix(moss_color, grass_color, smoothstep(0.35, 0.65, n));
	ground = mix(ground, dirt_color, smoothstep(0.62, 0.75, fbm(p * 0.8 + 7.0)) * 0.7);
	ground *= 0.7 + fbm(p * 4.0) * 0.6;

	ALBEDO = mix(ground, asphalt, road);
	float r_road = mix(road_roughness, puddle_roughness, puddle);
	r_road = mix(r_road, 0.95, crack);
	ROUGHNESS = mix(0.95, r_road, road);
	SPECULAR = mix(0.3, 0.6, road * puddle);
}
