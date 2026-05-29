<script context="module">
	import * as globals from "frontend/source/globals.js";
	import * as svelte from "svelte";
	import { page } from "$app/stores";
	import axios from "axios";
	import ItemsTable from "frontend/source/components/ItemsTable.svelte";
	const globals_r = globals.readonly;
</script>
<script>
	let items = [];
	let users = [];
	let read_overrides = new Map();
	let selected_item_ids = new Set();
	let move_target = "";
	let status_message = "";
	let is_loading = false;
	let hide_read = false;

	$: topic = $page.params.topic ? decodeURIComponent($page.params.topic) : "";
	$: distinct_subs = new Set(items.map(i => i.sub)).size;
	$: distinct_users = new Set(items.map(i => i.username)).size;

	async function load_items() {
		if (!topic) return;
		try {
			const r = await axios.get(`${globals_r.backend}/items_by_topic`, { params: { topic } });
			items = r.data.items || [];
			selected_item_ids = new Set();
			read_overrides = new Map();
		} catch (err) {
			console.error(err);
			status_message = `error loading items: ${err.message}`;
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

	function toggle_all() {
		if (selected_item_ids.size === items.length) {
			selected_item_ids = new Set();
		} else {
			selected_item_ids = new Set(items.map(i => i.id));
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
		// Group selected items by their source username to send one /move call per source.
		const by_source = new Map();
		for (const item of items) {
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
			await load_items();
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	svelte.onMount(() => {
		load_users();
	});

	// Reload items whenever the URL topic changes.
	let prev_topic = null;
	$: if (topic !== prev_topic) {
		prev_topic = topic;
		load_items();
	}
</script>

<svelte:head>
	<title>{topic} · {globals_r.app_name}</title>
</svelte:head>

<div class="d-flex flex-wrap justify-content-between align-items-center mb-3" style="gap:0.5rem">
	<div>
		<a href="/topics" class="text-info small">↩ back to /topics</a>
		<h3 class="m-0">{topic}</h3>
		<small class="text-muted">
			{items.length} items · {distinct_users} user{distinct_users === 1 ? "" : "s"} · {distinct_subs} sub{distinct_subs === 1 ? "" : "s"}
		</small>
	</div>
	<div class="d-flex align-items-center" style="gap:0.5rem">
		<label class="mb-0 small">
			<input type="checkbox" bind:checked={hide_read}/>
			hide read
		</label>
	</div>
</div>

{#if status_message}
	<div class="alert alert-info py-1 px-2">{status_message}</div>
{/if}

<div class="mb-2">
	<button type="button" class="btn btn-sm btn-outline-light" on:click={toggle_all}>
		{selected_item_ids.size === items.length && items.length > 0 ? "deselect all" : "select all"}
	</button>
	<small class="text-muted ml-2">{selected_item_ids.size} selected of {items.length}</small>
</div>

<ItemsTable
	items={items}
	show_username={true}
	hide_read={hide_read}
	bind:read_overrides={read_overrides}
	bind:selected_item_ids={selected_item_ids}
	on_set_read={handle_set_read}
/>

<div class="d-flex flex-wrap align-items-center mt-3" style="gap:0.5rem">
	<span>move {selected_item_ids.size} items →</span>
	<input
		bind:value={move_target}
		list="topic-move-target-options"
		type="text"
		placeholder="u/target_user"
		class="form-control form-control-sm bg-dark text-light border-secondary"
		style="max-width:300px; flex:1 1 180px"/>
	<datalist id="topic-move-target-options">
		{#each users as u (u.username)}
			<option value={u.username}/>
		{/each}
	</datalist>
	<button on:click={apply_move} disabled={is_loading || selected_item_ids.size === 0 || !move_target.trim()} class="btn btn-sm btn-warning">apply</button>
</div>
<small class="text-muted">
	moves preserve the source row's category (saved/upvoted/etc). selecting items from multiple users sends one move per source user.
</small>
