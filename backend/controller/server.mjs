process.env.backend = process.cwd();
process.env.frontend = process.env.backend.replace("backend", "frontend");

const _console_log = console.log.bind(console);
const _console_error = console.error.bind(console);
console.log = (...args) => _console_log(new Date().toISOString(), ...args);
console.error = (...args) => _console_error(new Date().toISOString(), ...args);

import express from "express";
import http from "http";
import fileupload from "express-fileupload";
import filesystem from "fs";
import path from "path";

const db = await import(`${process.env.backend}/model/db.mjs`);

const TEMP_DIR = path.join(process.env.backend, "data", "tmp");
if (!filesystem.existsSync(TEMP_DIR)) {
	filesystem.mkdirSync(TEMP_DIR, { recursive: true });
}

db.init();

const app = express();
const server = http.createServer(app);

app.use(express.json({ limit: "10mb" }));
app.use(fileupload({
	limits: { fileSize: 1024 * 1024 * 1024 } // 1 GiB
}));

if (process.env.RUN == "dev") {
	app.use((req, res, next) => {
		res.set("Access-Control-Allow-Origin", "*");
		res.set("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
		res.set("Access-Control-Allow-Headers", "Content-Type");
		if (req.method === "OPTIONS") return res.sendStatus(204);
		next();
	});
}

app.use("/", express.static(`${process.env.frontend}/build/`));

app.post("/open_db", async (req, res) => {
	try {
		const uploaded = req.files?.db;
		if (!uploaded) {
			res.status(400).send({ error: "no file uploaded (expected field 'db')" });
			return;
		}
		const tmp_path = path.join(TEMP_DIR, `upload_${Date.now()}.sqlite`);
		await uploaded.mv(tmp_path);
		try {
			db.merge_from_file(tmp_path);
		} finally {
			filesystem.promises.unlink(tmp_path).catch(() => null);
		}
		res.send({ ok: true });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.get("/users", (req, res) => {
	try {
		res.send({ users: db.get_users() });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.get("/subs", (req, res) => {
	try {
		const user = req.query.user;
		if (!user) {
			res.status(400).send({ error: "user query param required" });
			return;
		}
		res.send({ subs: db.get_subs(user) });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.get("/items", (req, res) => {
	try {
		const user = req.query.user;
		const sub = req.query.sub || "all";
		if (!user) {
			res.status(400).send({ error: "user query param required" });
			return;
		}
		res.send({ items: db.get_items(user, sub) });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.post("/move", (req, res) => {
	try {
		const { from_user, to_user, item_ids } = req.body || {};
		const result = db.move_items({ from_user, to_user, item_ids });
		res.send({ ok: true, ...result });
	} catch (err) {
		console.error(err);
		res.status(400).send({ error: String(err.message || err) });
	}
});

app.post("/set_read", (req, res) => {
	try {
		const { user, item_id, read } = req.body || {};
		if (!user || !item_id || read === undefined) {
			res.status(400).send({ error: "user, item_id, read are required" });
			return;
		}
		const result = db.set_read({ user, item_id, read: !!read });
		res.send({ ok: true, ...result });
	} catch (err) {
		console.error(err);
		res.status(400).send({ error: String(err.message || err) });
	}
});

app.get("/download_db", (req, res) => {
	const filepath = db.db_file_path();
	if (!filesystem.existsSync(filepath)) {
		res.status(404).send({ error: "no db file yet" });
		return;
	}
	res.download(filepath, "expanse_explorer.sqlite");
});

app.get("/api/topics", (req, res) => {
	try {
		res.send({ topics: db.get_topics() });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.post("/api/topics", (req, res) => {
	try {
		const { topic } = req.body || {};
		if (!topic || typeof topic !== "string" || !topic.trim()) {
			res.status(400).send({ error: "topic (non-empty string) required" });
			return;
		}
		const result = db.add_topic(topic.trim());
		res.status(201).send({ ok: true, ...result });
	} catch (err) {
		if (String(err.message || err).includes("UNIQUE")) {
			res.status(409).send({ error: "topic already exists" });
			return;
		}
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.patch("/api/topics", (req, res) => {
	try {
		const { old: old_name, new: new_name } = req.body || {};
		if (!old_name || !new_name || !old_name.trim() || !new_name.trim()) {
			res.status(400).send({ error: "old and new (non-empty strings) required" });
			return;
		}
		const result = db.rename_topic(old_name.trim(), new_name.trim());
		res.send({ ok: true, ...result });
	} catch (err) {
		if (err.code === "TOPIC_EXISTS") {
			res.status(409).send({ error: "target topic already exists" });
			return;
		}
		if (err.code === "TOPIC_NOT_FOUND") {
			res.status(404).send({ error: "topic not found" });
			return;
		}
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.delete("/api/topics/:topic", (req, res) => {
	try {
		const topic = req.params.topic;
		const result = db.delete_topic(topic);
		res.send({ ok: true, ...result });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.get("/all_subs", (req, res) => {
	try {
		const topic = req.query.topic;
		res.send({ subs: db.get_all_subs({ topic }) });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.post("/assign_topic", (req, res) => {
	try {
		const { subs, topic } = req.body || {};
		if (!Array.isArray(subs) || subs.length === 0) {
			res.status(400).send({ error: "subs (non-empty array) required" });
			return;
		}
		const result = db.assign_topic({ subs, topic });
		res.send({ ok: true, ...result });
	} catch (err) {
		console.error(err);
		res.status(400).send({ error: String(err.message || err) });
	}
});

app.get("/items_by_topic", (req, res) => {
	try {
		const topic = req.query.topic;
		if (!topic) {
			res.status(400).send({ error: "topic query param required" });
			return;
		}
		res.send({ items: db.get_items_by_topic({ topic }) });
	} catch (err) {
		console.error(err);
		res.status(500).send({ error: String(err.message || err) });
	}
});

app.all("*", (req, res) => {
	res.status(404).sendFile(`${process.env.frontend}/build/index.html`);
});

server.listen(Number.parseInt(process.env.PORT), "0.0.0.0", () => {
	console.log(`server (expanse_explorer) started on (localhost:${process.env.PORT})`);
});
