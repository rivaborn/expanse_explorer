<script context="module">
	import * as globals from "frontend/source/globals.js";
	import * as svelte from "svelte";
	import axios from "axios";
	const globals_r = globals.readonly;
</script>
<script>
	const ROW_H_DESKTOP = 36;
	const ROW_H_MOBILE = 56;
	const SCROLL_BUFFER_ROWS = 10;
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
	let item_sort_by = "created";
	let item_sort_order = "desc";

	let scroll_el;
	let scroll_top = 0;
	let viewport_h = 400;
	let row_h = ROW_H_DESKTOP;
	let scroll_raf = 0;

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

	$: visible_items = (() => {
		if (!hide_read) return sorted_items;
		return sorted_items.filter(i => !(read_overrides.has(i.id) ? read_overrides.get(i.id) : i.read_epoch));
	})();

	$: first_visible = Math.max(0, Math.floor(scroll_top / row_h) - SCROLL_BUFFER_ROWS);
	$: last_visible = Math.min(visible_items.length, Math.ceil((scroll_top + viewport_h) / row_h) + SCROLL_BUFFER_ROWS);
	$: window_rows = visible_items.slice(first_visible, last_visible);
	$: top_pad = first_visible * row_h;
	$: bot_pad = Math.max(0, (visible_items.length - last_visible) * row_h);

	$: if (scroll_el) {
		viewport_h = scroll_el.clientHeight;
	}

	function on_scroll() {
		if (scroll_raf) return;
		scroll_raf = requestAnimationFrame(() => {
			scroll_raf = 0;
			if (!scroll_el) return;
			scroll_top = scroll_el.scrollTop;
			viewport_h = scroll_el.clientHeight;
		});
	}

	function recompute_row_h() {
		row_h = window.matchMedia("(min-width: 576px)").matches ? ROW_H_DESKTOP : ROW_H_MOBILE;
	}

	function reset_scroll() {
		scroll_top = 0;
		if (scroll_el) scroll_el.scrollTop = 0;
	}

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
		read_overrides = new Map();
		items = [];
		subs = [];
		reset_scroll();
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
			reset_scroll();
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
			reset_scroll();
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

	async function set_read_remote(item_id, read) {
		try {
			await axios.post(`${globals_r.backend}/set_read`, {
				user: selected_user,
				item_id,
				read
			});
		} catch (err) {
			console.error(err);
		}
	}

	function read_epoch_of(i) {
		return read_overrides.has(i.id) ? read_overrides.get(i.id) : i.read_epoch;
	}

	function open_and_mark_read(i) {
		open_item(i.url);
		if (!read_epoch_of(i)) {
			read_overrides.set(i.id, Math.floor(Date.now() / 1000));
			read_overrides = read_overrides;
			set_read_remote(i.id, true);
		}
	}

	function toggle_read(i) {
		const new_read = !read_epoch_of(i);
		read_overrides.set(i.id, new_read ? Math.floor(Date.now() / 1000) : null);
		read_overrides = read_overrides;
		set_read_remote(i.id, new_read);
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
		recompute_row_h();
		const mq = window.matchMedia("(min-width: 576px)");
		const mq_handler = () => recompute_row_h();
		mq.addEventListener("change", mq_handler);
		const resize_handler = () => { if (scroll_el) viewport_h = scroll_el.clientHeight; };
		window.addEventListener("resize", resize_handler);
		return () => {
			mq.removeEventListener("change", mq_handler);
			window.removeEventListener("resize", resize_handler);
			if (scroll_raf) cancelAnimationFrame(scroll_raf);
		};
	});

	function fmt_date(epoch) {
		if (!epoch) return "-";
		return new Date(epoch * 1000).toISOString().slice(0, 16).replace("T", " ");
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

			<div class="border border-secondary rounded items-scroll" bind:this={scroll_el} on:scroll={on_scroll}>
				<table class="table table-sm table-dark mb-0">
					<thead>
						<tr>
							<th style="width:30px"></th>
							<th style="width:30px" title="read">✓</th>
							<th class="d-none d-sm-table-cell">type</th>
							<th>content</th>
							<th class="d-none d-md-table-cell">sub</th>
							<th class="d-none d-lg-table-cell">categories</th>
							<th class="d-none d-sm-table-cell" style="cursor:pointer; user-select:none" on:click={() => toggle_item_sort("created")}>
								created{item_sort_by === "created" ? (item_sort_order === "desc" ? " ↓" : " ↑") : ""}
							</th>
							<th style="cursor:pointer; user-select:none" on:click={() => toggle_item_sort("saved")}>
								saved{item_sort_by === "saved" ? (item_sort_order === "desc" ? " ↓" : " ↑") : ""}
							</th>
						</tr>
					</thead>
					<tbody>
						{#if top_pad > 0}
							<tr aria-hidden="true"><td colspan="8" style="padding:0; border:0"><div style="height:{top_pad}px"></div></td></tr>
						{/if}
						{#each window_rows as i (i.id)}
							{@const read_epoch = read_overrides.has(i.id) ? read_overrides.get(i.id) : i.read_epoch}
							<tr on:click={() => open_and_mark_read(i)} style="cursor:pointer; height:{row_h}px" class:item-read={!!read_epoch}>
								<td on:click|stopPropagation>
									<input type="checkbox" checked={selected_item_ids.has(i.id)} on:change={() => toggle_item(i.id)}/>
								</td>
								<td on:click|stopPropagation>
									<input type="checkbox" checked={!!read_epoch} on:change={() => toggle_read(i)} title={read_epoch ? `read ${fmt_date(read_epoch)}` : "mark read"}/>
								</td>
								<td class="d-none d-sm-table-cell">{i.type}</td>
								<td class="content-cell">
									{i.content}
									<div class="d-sm-none small text-muted">
										{i.type} · {i.sub}{#if i.categories} · {i.categories}{/if}
									</div>
								</td>
								<td class="d-none d-md-table-cell">{i.sub}</td>
								<td class="d-none d-lg-table-cell"><small>{i.categories}</small></td>
								<td class="d-none d-sm-table-cell"><small>{fmt_date(i.created_epoch)}</small></td>
								<td><small>{i.added_epoch ? fmt_date(i.added_epoch) : "-"}</small></td>
							</tr>
						{/each}
						{#if bot_pad > 0}
							<tr aria-hidden="true"><td colspan="8" style="padding:0; border:0"><div style="height:{bot_pad}px"></div></td></tr>
						{/if}
						{#if visible_items.length === 0}
							<tr><td colspan="8" class="text-muted text-center">no items</td></tr>
						{/if}
					</tbody>
				</table>
			</div>

			<div class="d-flex flex-wrap align-items-center mt-3" style="gap:0.5rem">
				<span>move {selected_item_ids.size} items →</span>
				<input bind:value={move_target} type="text" placeholder="u/target_user" class="form-control form-control-sm bg-dark text-light border-secondary" style="max-width:300px; flex:1 1 180px"/>
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
	.items-scroll {
		max-height: 50vh;
		overflow-y: auto;
	}
	.content-cell {
		word-break: break-word;
		max-width: 100%;
		overflow: hidden;
	}
	tr.item-read {
		opacity: 0.55;
	}
	@media (min-width: 768px) {
		.users-list {
			max-height: 70vh;
		}
		.content-cell {
			max-width: 300px;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
	}
</style>
