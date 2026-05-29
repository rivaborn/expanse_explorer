<script context="module">
	import * as globals from "frontend/source/globals.js";
	import * as svelte from "svelte";
	import axios from "axios";
	import ItemsTable from "frontend/source/components/ItemsTable.svelte";
	const globals_r = globals.readonly;
</script>
<script>
	let topics = [];
	let users = [];
	let items = [];
	let read_overrides = new Map();
	let selected_topic = null;
	let selected_sub = "all";
	let prev_selected_sub = "all";
	let selected_item_ids = new Set();
	let move_target = "";
	let status_message = "";
	let is_loading = false;
	let file_input;
	let sort_by_count = true;
	let hide_read = false;
	let initial_pick_done = false;

	$: sorted_topics = sort_by_count
		? [...topics].sort((a, b) => b.item_count - a.item_count || a.topic.localeCompare(b.topic))
		: [...topics].sort((a, b) => a.topic.localeCompare(b.topic));

	// Sub dropdown options: every sub appearing in the currently-loaded
	// items, with a per-sub item count. Re-derived whenever items change.
	$: sorted_subs_in_topic = (() => {
		const counts = new Map();
		for (const i of items) counts.set(i.sub, (counts.get(i.sub) || 0) + 1);
		return [...counts.entries()]
			.map(([sub, item_count]) => ({ sub, item_count }))
			.sort((a, b) => sort_by_count
				? b.item_count - a.item_count || a.sub.localeCompare(b.sub)
				: a.sub.localeCompare(b.sub));
	})();

	$: filtered_items = selected_sub === "all"
		? items
		: items.filter(i => i.sub === selected_sub);

	// Clear selection when the sub filter changes (parallels /by_user).
	$: if (selected_sub !== prev_selected_sub) {
		prev_selected_sub = selected_sub;
		selected_item_ids = new Set();
	}

	$: distinct_users = new Set(filtered_items.map(i => i.username)).size;
	$: distinct_subs = new Set(filtered_items.map(i => i.sub)).size;

	async function load_topics() {
		try {
			const r = await axios.get(`${globals_r.backend}/api/topics`);
			topics = r.data.topics || [];
		} catch (err) {
			console.error(err);
			status_message = `error loading topics: ${err.message}`;
		}
	}

	async function load_users() {
		try {
			const r = await axios.get(`${globals_r.backend}/users`);
			users = r.data.users || [];
		} catch (err) {
			console.error(err);
		}
	}

	async function select_topic(name) {
		selected_topic = name;
		selected_sub = "all";
		prev_selected_sub = "all";
		selected_item_ids = new Set();
		read_overrides = new Map();
		items = [];
		try {
			const r = await axios.get(`${globals_r.backend}/api/items_by_topic`, { params: { topic: name } });
			items = r.data.items || [];
		} catch (err) {
			console.error(err);
			status_message = `error loading items: ${err.message}`;
		}
	}

	function toggle_all() {
		if (selected_item_ids.size === filtered_items.length) {
			selected_item_ids = new Set();
		} else {
			selected_item_ids = new Set(filtered_items.map(i => i.id));
		}
	}

	async function set_read_remote(username, item_id, read) {
		try {
			await axios.post(`${globals_r.backend}/set_read`, { user: username, item_id, read });
		} catch (err) {
			console.error(err);
		}
	}

	function handle_set_read(item, new_read) {
		set_read_remote(item.username, item.id, new_read);
	}

	async function apply_move() {
		if (!move_target || selected_item_ids.size === 0) return;
		const target = move_target.trim().replace(/^u\//i, "");
		if (!target) return;
		const by_source = new Map();
		for (const item of filtered_items) {
			if (!selected_item_ids.has(item.id)) continue;
			const u = item.username;
			if (u === target) continue;
			if (!by_source.has(u)) by_source.set(u, []);
			by_source.get(u).push(item.id);
		}
		if (by_source.size === 0) {
			status_message = "nothing to move (target same as source on every selection)";
			return;
		}
		is_loading = true;
		status_message = "";
		let total = 0;
		try {
			for (const [from_user, item_ids] of by_source) {
				const r = await axios.post(`${globals_r.backend}/move`, {
					from_user, to_user: target, item_ids
				});
				total += r.data.moved_user_item_rows || 0;
			}
			status_message = `moved ${total} user_item rows from ${by_source.size} source user${by_source.size === 1 ? "" : "s"} → u/${target}`;
			move_target = "";
			await load_users();
			if (selected_topic) await select_topic(selected_topic);
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	async function upload_db() {
		const file = file_input.files?.[0];
		if (!file) return;
		is_loading = true;
		status_message = "uploading and merging...";
		try {
			const form = new FormData();
			form.append("db", file);
			await axios.post(`${globals_r.backend}/open_db`, form, {
				headers: { "Content-Type": "multipart/form-data" }
			});
			status_message = "merged successfully";
			file_input.value = "";
			await load_topics();
			await load_users();
			if (selected_topic) await select_topic(selected_topic);
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	function download_db() {
		window.open(`${globals_r.backend}/download_db`, "_blank");
	}

	svelte.onMount(async () => {
		await Promise.all([load_topics(), load_users()]);
	});

	// Auto-pick the highest-item-count category once topics arrive.
	$: if (!initial_pick_done && topics.length > 0 && !selected_topic) {
		const candidate = [...topics].sort((a, b) => b.item_count - a.item_count)[0];
		if (candidate && candidate.item_count > 0) {
			initial_pick_done = true;
			select_topic(candidate.topic);
		}
	}
</script>

<svelte:head>
	<title>{globals_r.app_name}</title>
</svelte:head>

<div class="d-flex flex-wrap justify-content-between align-items-center mb-3" style="gap:0.5rem">
	<h3 class="m-0">{globals_r.app_name}</h3>
	<div class="d-flex flex-wrap align-items-center" style="gap:0.5rem">
		<label class="mb-0 small">
			<input type="checkbox" bind:checked={sort_by_count}/>
			sort by count
		</label>
		<label class="mb-0 small">
			<input type="checkbox" bind:checked={hide_read}/>
			hide read
		</label>
		<input bind:this={file_input} type="file" accept=".sqlite,.db" on:change={upload_db} class="d-none" id="db_input"/>
		<label for="db_input" class="btn btn-sm btn-primary mb-0">load .sqlite</label>
		<button on:click={download_db} class="btn btn-sm btn-secondary">save .sqlite</button>
	</div>
</div>

{#if status_message}
	<div class="alert alert-info py-1 px-2">{status_message}</div>
{/if}

<div class="row">
	<div class="col-12 col-md-3 mb-3 mb-md-0">
		<h6>categories ({topics.length})</h6>
		<div class="list-group topics-list">
			{#each sorted_topics as t (t.topic)}
				<button
					type="button"
					class="list-group-item list-group-item-action bg-dark text-light border-secondary p-2"
					class:active={selected_topic === t.topic}
					on:click={() => select_topic(t.topic)}
				>
					<div class="d-flex justify-content-between">
						<span>{t.topic}</span>
						<small class="text-muted">{t.item_count}</small>
					</div>
					<small class="text-muted">{t.sub_count} sub{t.sub_count === 1 ? "" : "s"}</small>
				</button>
			{/each}
			{#if topics.length === 0}
				<div class="text-muted small">no categories yet</div>
			{/if}
		</div>
	</div>

	<div class="col-12 col-md-9">
		{#if selected_topic}
			<div class="d-flex flex-wrap align-items-center mb-2" style="gap:0.5rem">
				<b>{selected_topic}</b>
				<label class="mb-0 small">sub:</label>
				<select bind:value={selected_sub} class="form-control form-control-sm bg-dark text-light border-secondary" style="max-width:300px; flex:1 1 200px">
					<option value="all">all ({items.length})</option>
					{#each sorted_subs_in_topic as s (s.sub)}
						<option value={s.sub}>{s.sub} ({s.item_count})</option>
					{/each}
				</select>
				<small class="text-muted">
					{filtered_items.length} items · {distinct_users} user{distinct_users === 1 ? "" : "s"} · {distinct_subs} sub{distinct_subs === 1 ? "" : "s"}
				</small>
			</div>

			<div class="mb-2">
				<button type="button" class="btn btn-sm btn-outline-light" on:click={toggle_all}>
					{selected_item_ids.size === filtered_items.length && filtered_items.length > 0 ? "deselect all" : "select all"}
				</button>
				<small class="text-muted ml-2">{selected_item_ids.size} selected of {filtered_items.length}</small>
			</div>

			<ItemsTable
				items={filtered_items}
				show_username={true}
				hide_read={hide_read}
				bind:read_overrides={read_overrides}
				bind:selected_item_ids={selected_item_ids}
				on_set_read={handle_set_read}
			/>

			<div class="d-flex flex-wrap align-items-center mt-3" style="gap:0.5rem">
				<span>move {selected_item_ids.size} items →</span>
				<input bind:value={move_target} list="cat-move-target-options" type="text" placeholder="u/target_user" class="form-control form-control-sm bg-dark text-light border-secondary" style="max-width:300px; flex:1 1 180px"/>
				<datalist id="cat-move-target-options">
					{#each users as u (u.username)}
						<option value={u.username}/>
					{/each}
				</datalist>
				<button on:click={apply_move} disabled={is_loading || selected_item_ids.size === 0 || !move_target.trim()} class="btn btn-sm btn-warning">apply</button>
			</div>
			<small class="text-muted">
				selecting items from multiple users sends one move per source user. unmapped subs don't show up here — assign them in <a href="/topics">organize by category</a>.
			</small>
		{:else}
			<div class="text-muted mt-5 text-center">
				{topics.length === 0
					? "load a .sqlite to begin"
					: "pick a category from the left"}
			</div>
		{/if}
	</div>
</div>

<style>
	.topics-list {
		max-height: 40vh;
		overflow-y: auto;
	}
	@media (min-width: 768px) {
		.topics-list {
			max-height: 75vh;
		}
	}
</style>
