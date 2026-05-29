<script context="module">
	import * as globals from "frontend/source/globals.js";
	import * as svelte from "svelte";
	import axios from "axios";
	import ItemsTable from "frontend/source/components/ItemsTable.svelte";
	const globals_r = globals.readonly;
</script>
<script>
	const LARGE_USER_THRESHOLD = 1000;

	let users = [];
	let subs = [];
	let items = [];
	let read_overrides = new Map();
	let selected_user = null;
	let selected_sub = "all";
	let selected_item_ids = new Set();
	let move_target = "";
	let status_message = "";
	let is_loading = false;
	let file_input;
	let sort_by_count = false;
	let hide_read = false;

	$: sorted_users = sort_by_count
		? [...users].sort((a, b) => b.item_count - a.item_count || a.username.localeCompare(b.username))
		: [...users].sort((a, b) => a.username.localeCompare(b.username));

	$: sorted_subs = sort_by_count
		? [...subs].sort((a, b) => b.item_count - a.item_count || a.sub.localeCompare(b.sub))
		: [...subs].sort((a, b) => a.sub.localeCompare(b.sub));

	async function load_users() {
		try {
			const response = await axios.get(`${globals_r.backend}/users`);
			users = response.data.users || [];
		} catch (err) {
			console.error(err);
			status_message = `error loading users: ${err.message}`;
		}
	}

	async function select_user(username) {
		selected_user = username;
		selected_sub = "all";
		selected_item_ids = new Set();
		read_overrides = new Map();
		items = [];
		subs = [];
		const u = users.find(x => x.username === username);
		try {
			const subs_resp = await axios.get(`${globals_r.backend}/subs`, { params: { user: username } });
			subs = subs_resp.data.subs || [];
			if (u && u.item_count > LARGE_USER_THRESHOLD && subs.length > 0) {
				const largest = subs.reduce((a, b) => b.item_count > a.item_count ? b : a);
				selected_sub = largest.sub;
			}
			const items_resp = await axios.get(`${globals_r.backend}/items`, { params: { user: username, sub: selected_sub } });
			items = items_resp.data.items || [];
		} catch (err) {
			console.error(err);
			status_message = `error loading user data: ${err.message}`;
		}
	}

	async function change_sub() {
		if (!selected_user) return;
		selected_item_ids = new Set();
		try {
			const response = await axios.get(`${globals_r.backend}/items`, { params: { user: selected_user, sub: selected_sub } });
			items = response.data.items || [];
		} catch (err) {
			console.error(err);
			status_message = `error loading items: ${err.message}`;
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
		set_read_remote(selected_user, item.id, new_read);
	}

	async function apply_move() {
		if (!selected_user || !move_target || selected_item_ids.size === 0) return;
		const target = move_target.trim().replace(/^u\//i, "");
		if (!target) return;
		if (target === selected_user) {
			status_message = "from_user and to_user must differ";
			return;
		}
		is_loading = true;
		status_message = "";
		try {
			const response = await axios.post(`${globals_r.backend}/move`, {
				from_user: selected_user,
				to_user: target,
				item_ids: Array.from(selected_item_ids)
			});
			status_message = `moved ${response.data.moved_user_item_rows} user_item rows from u/${selected_user} to u/${target}`;
			move_target = "";
			await load_users();
			await select_user(selected_user);
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
			await load_users();
			if (selected_user) await select_user(selected_user);
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

	svelte.onMount(() => {
		load_users();
	});
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
		<h6>users ({users.length})</h6>
		<div class="list-group users-list">
			{#each sorted_users as u (u.username)}
				<button
					type="button"
					class="list-group-item list-group-item-action bg-dark text-light border-secondary p-2"
					class:active={selected_user === u.username}
					on:click={() => select_user(u.username)}
				>
					<div class="d-flex justify-content-between">
						<span>u/{u.username}</span>
						<small class="text-muted">{u.item_count}</small>
					</div>
				</button>
			{/each}
			{#if users.length === 0}
				<div class="text-muted small">no users yet — load a .sqlite</div>
			{/if}
		</div>
	</div>

	<div class="col-12 col-md-9">
		{#if selected_user}
			<div class="d-flex flex-wrap align-items-center mb-2" style="gap:0.5rem">
				<b>u/{selected_user}</b>
				<label class="mb-0 small">sub:</label>
				<select bind:value={selected_sub} on:change={change_sub} class="form-control form-control-sm bg-dark text-light border-secondary" style="max-width:300px; flex:1 1 200px">
					<option value="all">all ({items.length === 0 ? 0 : subs.reduce((a, b) => a + b.item_count, 0)})</option>
					{#each sorted_subs as s}
						<option value={s.sub}>{s.sub} ({s.item_count})</option>
					{/each}
				</select>
			</div>

			<div class="mb-2">
				<button type="button" class="btn btn-sm btn-outline-light" on:click={toggle_all}>
					{selected_item_ids.size === items.length && items.length > 0 ? "deselect all" : "select all"}
				</button>
				<small class="text-muted ml-2">{selected_item_ids.size} selected of {items.length}</small>
			</div>

			<ItemsTable
				items={items}
				show_username={false}
				hide_read={hide_read}
				bind:read_overrides={read_overrides}
				bind:selected_item_ids={selected_item_ids}
				on_set_read={handle_set_read}
			/>

			<div class="d-flex flex-wrap align-items-center mt-3" style="gap:0.5rem">
				<span>move {selected_item_ids.size} items →</span>
				<input bind:value={move_target} list="move-target-options" type="text" placeholder="u/target_user" class="form-control form-control-sm bg-dark text-light border-secondary" style="max-width:300px; flex:1 1 180px"/>
				<datalist id="move-target-options">
					{#each users as u (u.username)}
						{#if u.username !== selected_user}<option value={u.username}/>{/if}
					{/each}
				</datalist>
				<button on:click={apply_move} disabled={is_loading || selected_item_ids.size === 0 || !move_target.trim()} class="btn btn-sm btn-warning">apply</button>
			</div>
			<small class="text-muted">click a row to open in browser (also marks read). unknown target users get a placeholder row in user_.</small>
		{:else}
			<div class="text-muted mt-5 text-center">select a user{#if users.length > 0}{` `}above{/if}</div>
		{/if}
	</div>
</div>

<style>
	.users-list {
		max-height: 40vh;
		overflow-y: auto;
	}
	@media (min-width: 768px) {
		.users-list {
			max-height: 70vh;
		}
	}
</style>
