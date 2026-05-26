import * as vite from "@sveltejs/kit/vite";

const frontend = process.cwd();

export default {
	plugins: [vite.sveltekit()],
	resolve: {
		alias: {
			frontend: frontend
		}
	},
	server: {
		host: "0.0.0.0",
		port: Number.parseInt(process.env.PORT),
		strictPort: true,
		proxy: {
			"/backend": {
				rewrite: (path) => path.replace(/^(\/backend)/, ""),
				target: `http://localhost:${Number.parseInt(process.env.PORT) + 1}`,
				secure: false,
				changeOrigin: true,
				ws: true
			}
		},
		fs: {
			strict: true,
			allow: [frontend]
		},
		watch: {
			usePolling: true
		}
	}
};
