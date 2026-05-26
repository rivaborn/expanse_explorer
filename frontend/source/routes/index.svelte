<script context="module">
	import * as globals from "frontend/source/globals.js";
	import * as svelte from "svelte";
	import axios from "axios";
	const globals_r = globals.readonly;
</script>
<script>
	let users = [];
	let subs = [];
	let items = [];
	let selected_user = null;
	let selected_sub = "all";
	let selected_item_ids = new Set();
	let move_target = "";
	let status_message = "";
	let is_loading = false;
	let file_input;
	let sort_by_count = false;
	let item_sort_by = "created";
	let item_sort_order = "desc";

	$: sorted_users = sort_by_count
		? [...users].sort((a, b) => b.item_count - a.item_count || a.username.localeCompare(b.username))
		: [...users].sort((a, b) => a.username.localeCompare(b.username));

	$: sorted_subs = sort_by_count
		? [...subs].sort((a, b) => b.item_count - a.item_count || a.sub.localeCompare(b.sub))
		: [...subs].sort((a, b) => a.sub.localeCompare(b.sub));

	$: sorted_items = (() => {
		const key = item_sort_by === "saved" ? "added_epoch" : "created_epoch";
		const sign = item_sort_order === "asc" ? 1 : -1;
		return [...items].sort((a, b) => {
			const av = a[key];
			const bv = b[key];
			if (av == null && bv == null) return 0;
			if (av == null) return 1;
			if (bv == null) return -1;
			return sign * (av - bv);
		});
	})();

	function toggle_item_sort(col) {
		if (item_sort_by === col) {
			item_sort_order = item_sort_order === "desc" ? "asc" : "desc";
		} else {
			item_sort_by = col;
			item_sort_order = "desc";
		}
	}

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
		items = [];
		subs = [];
		try {
			const [subs_resp, items_resp] = await Promise.all([
				axios.get(`${globals_r.backend}/subs`, { params: { user: username } }),
				axios.get(`${globals_r.backend}/items`, { params: { user: username, sub: "all" } })
			]);
			subs = subs_resp.data.subs || [];
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

	function toggle_item(item_id) {
		if (selected_item_ids.has(item_id)) {
			selected_item_ids.delete(item_id);
		} else {
			selected_item_ids.add(item_id);
		}
		selected_item_ids = selected_item_ids;
	}

	function toggle_all() {
		if (selected_item_ids.size === items.length) {
			selected_item_ids = new Set();
		} else {
			selected_item_ids = new Set(items.map(i => i.id));
		}
	}

	function open_item(url) {
		if (url) window.open(url, "_blank");
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

	function fmt_date(epoch) {
		if (!epoch) return "-";
		return new Date(epoch * 1000).toISOString().slice(0, 16).replace("T", " ");
	}
</script>

<svelte:head>
	<title>{globals_r.app_name}</title>
</svelte:head>

<div class="d-flex justify-content-between align-items-center mb-3">
	<h3 class="m-0">{globals_r.app_name}</h3>
	<div class="d-flex align-items-center">
		<label class="mb-0 mr-3 small">
			<input type="checkbox" bind:checked={sort_by_count}/>
			sort by count
		</label>
		<input bind:this={file_input} type="file" accept=".sqlite,.db" on:change={upload_db} class="d-none" id="db_input"/>
		<label for="db_input" class="btn btn-sm btn-primary mb-0 mr-2">load .sqlite</label>
		<button on:click={download_db} class="btn btn-sm btn-secondary">save .sqlite</button>
	</div>
</div>

{#if status_message}
	<div class="alert alert-info py-1 px-2">{status_message}</div>
{/if}

<div class="row">
	<div class="col-3">
		<h6>users ({users.length})</h6>
		<div class="list-group">
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

	<div class="col-9">
		{#if selected_user}
			<div class="d-flex align-items-center mb-2">
				<b class="mr-3">u/{selected_user}</b>
				<label class="mb-0 mr-2 small">sub:</label>
				<select bind:value={selected_sub} on:change={change_sub} class="form-control form-control-sm bg-dark text-light border-secondary" style="max-width:300px">
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

			<div class="border border-secondary rounded" style="max-height:50vh; overflow-y:auto">
				<table class="table table-sm table-dark mb-0">
					<thead>
						<tr>
							<th style="width:30px"></th>
							<th>type</th>
							<th>content</th>
							<th>sub</th>
							<th>categories</th>
							<th style="cursor:pointer; user-select:none" on:click={() => toggle_item_sort("created")}>
								created{item_sort_by === "created" ? (item_sort_order === "desc" ? " ↓" : " ↑") : ""}
							</th>
							<th style="cursor:pointer; user-select:none" on:click={() => toggle_item_sort("saved")}>
								saved{item_sort_by === "saved" ? (item_sort_order === "desc" ? " ↓" : " ↑") : ""}
							</th>
						</tr>
					</thead>
					<tbody>
						{#each sorted_items as i (i.id)}
							<tr on:click={() => open_item(i.url)} style="cursor:pointer">
								<td on:click|stopPropagation>
									<input type="checkbox" checked={selected_item_ids.has(i.id)} on:change={() => toggle_item(i.id)}/>
								</td>
								<td>{i.type}</td>
								<td class="text-truncate" style="max-width:300px">{i.content}</td>
								<td>{i.sub}</td>
								<td><small>{i.categories}</small></td>
								<td><small>{fmt_date(i.created_epoch)}</small></td>
								<td><small>{i.added_epoch ? fmt_date(i.added_epoch) : "-"}</small></td>
							</tr>
						{/each}
						{#if sorted_items.length === 0}
							<tr><td colspan="7" class="text-muted text-center">no items</td></tr>
						{/if}
					</tbody>
				</table>
			</div>

			<div class="d-flex align-items-center mt-3">
				<span class="mr-2">move {selected_item_ids.size} items →</span>
				<input bind:value={move_target} type="text" placeholder="u/target_user" class="form-control form-control-sm bg-dark text-light border-secondary mr-2" style="max-width:300px"/>
				<button on:click={apply_move} disabled={is_loading || selected_item_ids.size === 0 || !move_target.trim()} class="btn btn-sm btn-warning">apply</button>
			</div>
			<small class="text-muted">click a row to open in browser. unknown target users get a placeholder row in user_.</small>
		{:else}
			<div class="text-muted mt-5 text-center">select a user on the left</div>
		{/if}
	</div>
</div>
