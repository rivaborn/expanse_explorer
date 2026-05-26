import * as env_static_public from "$env/static/public";

const readonly = {
	app_name: "expanse explorer",
	description: "browse and reorganize an Expanse .sqlite export locally",
	backend: (env_static_public.RUN == "dev" ? "/backend" : "")
};

export {
	readonly
};
