import filesystem from "fs";
import path from "path";
import better_sqlite3 from "better-sqlite3";

const DATA_DIR = `${process.env.backend}/data`;
const DB_PATH = path.join(DATA_DIR, "current.sqlite");

let db = null;

function init() {
	if (!filesystem.existsSync(DATA_DIR)) {
		filesystem.mkdirSync(DATA_DIR, { recursive: true });
	}
	db = better_sqlite3(DB_PATH);
	db.pragma("journal_mode = WAL");
	db.pragma("foreign_keys = ON");
	db.exec(`
		create table if not exists user_ (
			username text primary key,
			reddit_api_refresh_token_encrypted text,
			category_sync_info text,
			last_updated_epoch integer,
			last_active_epoch integer
		);
		create table if not exists item (
			id text primary key,
			type text not null,
			content text not null,
			author text not null,
			sub text not null,
			url text not null,
			created_epoch integer not null
		);
		create table if not exists item_fn_to_import (
			id text primary key,
			fn_prefix text not null
		);
		create table if not exists user_item (
			username text not null,
			category text not null,
			item_id text not null,
			added_epoch integer,
			read_epoch integer,
			unique (username, category, item_id)
		);
		create table if not exists item_sub_icon_url (
			sub text primary key,
			url text not null
		);
		create table if not exists moves (
			item_id text not null,
			from_username text not null,
			from_category text not null,
			to_username text not null,
			to_category text not null,
			moved_at_epoch integer not null,
			primary key (item_id, from_username, from_category)
		);
		create table if not exists topic (
			topic text primary key
		);
		create table if not exists sub_topic (
			sub   text primary key,
			topic text not null references topic(topic) on delete cascade on update cascade
		);
		create index if not exists idx_sub_topic_topic on sub_topic(topic);
	`);

	const user_item_cols = db.prepare("pragma table_info(user_item)").all().map(c => c.name);
	if (!user_item_cols.includes("added_epoch")) {
		db.exec("alter table user_item add column added_epoch integer;");
	}
	if (!user_item_cols.includes("read_epoch")) {
		db.exec("alter table user_item add column read_epoch integer;");
	}

	const seed_topics = [
		"Jokes & Humor",
		"Reddit Stories & Best-Of",
		"AITA & Judgement",
		"Marriage & Divorce",
		"Infidelity",
		"Relationship Advice",
		"Sex & Intimacy",
		"Non-monogamy",
		"Erotica & NSFW",
		"Books & Reading",
		"Sci-Fi & Fantasy Books",
		"Long-form Reading & Articles",
		"Medicine & Healthcare",
		"Finance & Investing",
		"Real Estate & Housing",
		"Tech & Self-hosting",
		"AI & LLMs",
		"Video Games (console/PC)",
		"Handheld & Portable Gaming",
		"Gaming Deals & Bundles",
		"Demographics Q&A",
		"Generic Q&A",
		"Politics & Society",
		"News, Data & Tech Culture",
		"Religion",
		"TV, Movies & Sitcoms",
		"Memes & Random Visuals",
		"Writing & Creating",
		"Body, Fitness & Appearance",
		"Miscellaneous"
	];
	const insert_topic = db.prepare("insert or ignore into topic(topic) values (?)");
	const seed_tx = db.transaction(() => { for (const t of seed_topics) insert_topic.run(t); });
	seed_tx();
}

function get_db() {
	if (!db) init();
	return db;
}

function merge_from_file(uploaded_path) {
	const d = get_db();
	d.exec(`attach database '${uploaded_path.replaceAll("'", "''")}' as upload;`);
	try {
		d.exec("begin;");

		d.exec(`
			insert into main.user_ (username, reddit_api_refresh_token_encrypted, category_sync_info, last_updated_epoch, last_active_epoch)
			select u.username, u.reddit_api_refresh_token_encrypted, u.category_sync_info, u.last_updated_epoch, u.last_active_epoch
			from upload.user_ u
			where true
			on conflict (username) do update set
				reddit_api_refresh_token_encrypted = coalesce(excluded.reddit_api_refresh_token_encrypted, main.user_.reddit_api_refresh_token_encrypted),
				category_sync_info = coalesce(excluded.category_sync_info, main.user_.category_sync_info),
				last_updated_epoch = max(coalesce(excluded.last_updated_epoch, 0), coalesce(main.user_.last_updated_epoch, 0)),
				last_active_epoch = max(coalesce(excluded.last_active_epoch, 0), coalesce(main.user_.last_active_epoch, 0));
		`);

		d.exec(`
			insert into main.item (id, type, content, author, sub, url, created_epoch)
			select id, type, content, author, sub, url, created_epoch
			from upload.item
			where true
			on conflict (id) do nothing;
		`);

		d.exec(`
			insert into main.item_sub_icon_url (sub, url)
			select sub, url
			from upload.item_sub_icon_url
			where true
			on conflict (sub) do update set url = excluded.url;
		`);

		d.exec(`
			insert into main.item_fn_to_import (id, fn_prefix)
			select id, fn_prefix
			from upload.item_fn_to_import
			where true
			on conflict (id) do nothing;
		`);

		const upload_user_item_cols = d.prepare("pragma upload.table_info(user_item)").all().map(c => c.name);
		const has_added_epoch_upload = upload_user_item_cols.includes("added_epoch");
		const upload_added_epoch_expr = has_added_epoch_upload ? "u.added_epoch" : "null";
		d.exec(`
			insert into main.user_item (username, category, item_id, added_epoch)
			select u.username, u.category, u.item_id, ${upload_added_epoch_expr}
			from upload.user_item u
			where not exists (
				select 1 from main.user_item e
				where e.username = u.username and e.category = u.category and e.item_id = u.item_id
			)
			and not exists (
				select 1 from main.moves m
				where m.from_username = u.username and m.item_id = u.item_id
			);
		`);

		if (has_added_epoch_upload) {
			d.exec(`
				update user_item
				set added_epoch = (
					select u.added_epoch
					from upload.user_item u
					where u.username = user_item.username
					  and u.category = user_item.category
					  and u.item_id = user_item.item_id
				)
				where user_item.added_epoch is null
				  and exists (
					select 1 from upload.user_item u
					where u.username = user_item.username
					  and u.category = user_item.category
					  and u.item_id = user_item.item_id
					  and u.added_epoch is not null
				  );
			`);
		}

		d.exec("commit;");
	} catch (err) {
		d.exec("rollback;");
		throw err;
	} finally {
		d.exec("detach database upload;");
	}
}

function get_users() {
	const d = get_db();
	return d.prepare(`
		select u.username,
		       coalesce(c.item_count, 0) as item_count,
		       u.last_updated_epoch
		from user_ u
		left join (
			select username, count(distinct item_id) as item_count
			from user_item
			group by username
		) c on c.username = u.username
		order by item_count desc, u.username asc;
	`).all();
}

function get_subs(username) {
	const d = get_db();
	return d.prepare(`
		select i.sub, count(*) as item_count
		from item i
		inner join user_item ui on ui.item_id = i.id
		where ui.username = ?
		group by i.sub
		order by item_count desc, i.sub asc;
	`).all(username).map(r => ({ sub: r.sub, item_count: r.item_count }));
}

function get_items(username, sub) {
	const d = get_db();
	const params = [username];
	let sub_clause = "";
	if (sub && sub !== "all") {
		sub_clause = "and i.sub = ?";
		params.push(sub);
	}
	return d.prepare(`
		select i.id, i.type, i.content, i.author, i.sub, i.url, i.created_epoch,
		       group_concat(distinct ui.category) as categories,
		       min(ui.added_epoch) as added_epoch,
		       max(ui.read_epoch) as read_epoch
		from item i
		inner join user_item ui on ui.item_id = i.id
		where ui.username = ? ${sub_clause}
		group by i.id
		order by i.created_epoch desc;
	`).all(...params);
}

function move_items({ from_user, to_user, item_ids }) {
	if (!from_user || !to_user || !Array.isArray(item_ids) || item_ids.length === 0) {
		throw new Error("from_user, to_user, item_ids are required");
	}
	if (from_user === to_user) {
		throw new Error("from_user and to_user must differ");
	}

	const d = get_db();
	const now_epoch = Math.floor(Date.now() / 1000);

	const ensure_user = d.prepare(`
		insert into user_ (username, reddit_api_refresh_token_encrypted, category_sync_info, last_updated_epoch, last_active_epoch)
		values (?, null, null, null, ?)
		on conflict (username) do nothing;
	`);
	const select_rows = d.prepare(`
		select category, added_epoch, read_epoch from user_item
		where username = ? and item_id = ?;
	`);
	const record_move = d.prepare(`
		insert into moves (item_id, from_username, from_category, to_username, to_category, moved_at_epoch)
		values (?, ?, ?, ?, ?, ?)
		on conflict (item_id, from_username, from_category) do update set
			to_username = excluded.to_username,
			to_category = excluded.to_category,
			moved_at_epoch = excluded.moved_at_epoch;
	`);
	const delete_existing = d.prepare(`
		delete from user_item where username = ? and category = ? and item_id = ?;
	`);
	const insert_target = d.prepare(`
		insert into user_item (username, category, item_id, added_epoch, read_epoch) values (?, ?, ?, ?, ?)
		on conflict (username, category, item_id) do nothing;
	`);

	let moved_count = 0;
	const tx = d.transaction(() => {
		ensure_user.run(to_user, now_epoch);

		for (const item_id of item_ids) {
			const rows = select_rows.all(from_user, item_id);
			for (const row of rows) {
				record_move.run(item_id, from_user, row.category, to_user, row.category, now_epoch);
				delete_existing.run(from_user, row.category, item_id);
				insert_target.run(to_user, row.category, item_id, row.added_epoch, row.read_epoch);
				moved_count++;
			}
		}
	});
	tx();

	return { moved_user_item_rows: moved_count };
}

function set_read({ user, item_id, read }) {
	if (!user || !item_id) {
		throw new Error("user and item_id are required");
	}
	const d = get_db();
	const epoch = read ? Math.floor(Date.now() / 1000) : null;
	const info = d.prepare(`
		update user_item set read_epoch = ?
		where username = ? and item_id = ?;
	`).run(epoch, user, item_id);
	return { updated_rows: info.changes, read_epoch: epoch };
}

function db_file_path() {
	return DB_PATH;
}

function get_topics() {
	const d = get_db();
	return d.prepare(`
		select t.topic,
		       coalesce(sc.sub_count, 0)  as sub_count,
		       coalesce(ic.item_count, 0) as item_count
		from topic t
		left join (
			select topic, count(*) as sub_count
			from sub_topic
			group by topic
		) sc on sc.topic = t.topic
		left join (
			select st.topic, count(*) as item_count
			from sub_topic st
			inner join item i on i.sub = st.sub
			group by st.topic
		) ic on ic.topic = t.topic
		order by item_count desc, t.topic asc;
	`).all();
}

function add_topic(topic) {
	if (!topic || typeof topic !== "string") throw new Error("topic required");
	const d = get_db();
	const info = d.prepare("insert into topic(topic) values (?)").run(topic);
	return { created: info.changes > 0 };
}

function rename_topic(old_name, new_name) {
	if (!old_name || !new_name) throw new Error("old and new topic names required");
	if (old_name === new_name) return { renamed: false };
	const d = get_db();
	const exists_new = d.prepare("select 1 from topic where topic = ?").get(new_name);
	if (exists_new) {
		const err = new Error("target topic already exists");
		err.code = "TOPIC_EXISTS";
		throw err;
	}
	const info = d.prepare("update topic set topic = ? where topic = ?").run(new_name, old_name);
	if (info.changes === 0) {
		const err = new Error("topic not found");
		err.code = "TOPIC_NOT_FOUND";
		throw err;
	}
	return { renamed: true };
}

function delete_topic(topic) {
	if (!topic) throw new Error("topic required");
	const d = get_db();
	const sub_count = d.prepare("select count(*) as n from sub_topic where topic = ?").get(topic).n;
	const info = d.prepare("delete from topic where topic = ?").run(topic);
	return { deleted: info.changes > 0, cascaded_sub_topic_rows: sub_count };
}

function get_all_subs({ topic } = {}) {
	const d = get_db();
	let sql, params;
	if (topic === undefined || topic === null || topic === "") {
		sql = `
			select i.sub,
			       count(*) as item_count,
			       st.topic as topic
			from item i
			left join sub_topic st on st.sub = i.sub
			group by i.sub
			order by item_count desc, i.sub asc;
		`;
		params = [];
	} else if (topic === "__none__") {
		sql = `
			select i.sub,
			       count(*) as item_count,
			       null as topic
			from item i
			left join sub_topic st on st.sub = i.sub
			where st.sub is null
			group by i.sub
			order by item_count desc, i.sub asc;
		`;
		params = [];
	} else {
		sql = `
			select i.sub,
			       count(*) as item_count,
			       st.topic as topic
			from item i
			inner join sub_topic st on st.sub = i.sub
			where st.topic = ?
			group by i.sub
			order by item_count desc, i.sub asc;
		`;
		params = [topic];
	}
	return d.prepare(sql).all(...params);
}

function assign_topic({ subs, topic }) {
	if (!Array.isArray(subs) || subs.length === 0) throw new Error("subs array required");
	const d = get_db();
	let count = 0;
	const tx = d.transaction(() => {
		if (topic === null || topic === undefined) {
			const del = d.prepare("delete from sub_topic where sub = ?");
			for (const s of subs) {
				const info = del.run(s);
				count += info.changes;
			}
		} else {
			d.prepare("insert or ignore into topic(topic) values (?)").run(topic);
			const upsert = d.prepare(`
				insert into sub_topic(sub, topic) values (?, ?)
				on conflict(sub) do update set topic = excluded.topic;
			`);
			for (const s of subs) {
				upsert.run(s, topic);
				count++;
			}
		}
	});
	tx();
	return { assigned_count: count };
}

function get_items_by_topic({ topic }) {
	if (!topic) throw new Error("topic required");
	const d = get_db();
	return d.prepare(`
		select i.id, i.type, i.content, i.author, i.sub, i.url, i.created_epoch,
		       ui.username,
		       group_concat(distinct ui.category) as categories,
		       min(ui.added_epoch) as added_epoch,
		       max(ui.read_epoch) as read_epoch
		from item i
		inner join sub_topic st on st.sub = i.sub
		inner join user_item ui on ui.item_id = i.id
		where st.topic = ?
		group by i.id, ui.username
		order by i.created_epoch desc;
	`).all(topic);
}

export {
	init,
	get_db,
	merge_from_file,
	get_users,
	get_subs,
	get_items,
	move_items,
	set_read,
	db_file_path,
	get_topics,
	add_topic,
	rename_topic,
	delete_topic,
	get_all_subs,
	assign_topic,
	get_items_by_topic
};
