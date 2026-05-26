import adapter_static from "@sveltejs/adapter-static";

export default {
	extensions: [".svelte"],
	kit: {
		adapter: adapter_static({
			fallback: true
		}),
		files: {
			template: "./source/app.html",
			routes: "./source/routes/",
			hooks: "./source/hooks.js",
			assets: "./static/"
		},
		trailingSlash: "never",
		env: {
			publicPrefix: ""
		}
	}
};
