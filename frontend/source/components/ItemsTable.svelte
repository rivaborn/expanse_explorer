<script>
	import * as svelte from "svelte";

	const ROW_H_DESKTOP = 36;
	const ROW_H_MOBILE = 56;
	const SCROLL_BUFFER_ROWS = 10;

	export let items = [];
	export let show_username = false;
	export let hide_read = false;
	export let read_overrides = new Map();
	export let selected_item_ids = new Set();
	export let on_set_read = () => {};

	let sort_by = "created";
	let sort_order = "desc";

	let scroll_el;
	let scroll_top = 0;
	let viewport_h = 400;
	let row_h = ROW_H_DESKTOP;
	let scroll_raf = 0;

	$: sorted_items = (() => {
		const key = sort_by === "saved" ? "added_epoch" : "created_epoch";
		const sign = sort_order === "asc" ? 1 : -1;
		return [...items].sort((a, b) => {
			const av = a[key];
			const bv = b[key];
			if (av == null && bv == null) return 0;
			if (av == null) return 1;
			if (bv == null) return -1;
			return sign * (av - bv);
		});
	})();

	$: visible_items = hide_read
		? sorted_items.filter(i => !(read_overrides.has(i.id) ? read_overrides.get(i.id) : i.read_epoch))
		: sorted_items;

	$: first_visible = Math.max(0, Math.floor(scroll_top / row_h) - SCROLL_BUFFER_ROWS);
	$: last_visible = Math.min(visible_items.length, Math.ceil((scroll_top + viewport_h) / row_h) + SCROLL_BUFFER_ROWS);
	$: window_rows = visible_items.slice(first_visible, last_visible);
	$: top_pad = first_visible * row_h;
	$: bot_pad = Math.max(0, (visible_items.length - last_visible) * row_h);

	$: if (scroll_el) {
		viewport_h = scroll_el.clientHeight;
	}

	// total visible columns: 2 fixed (select + read) + content + sub + categories + 2 date cols
	// + type + (optional username) = 8 + (show_username ? 1 : 0)
	$: total_cols = show_username ? 9 : 8;

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

	function toggle_sort(col) {
		if (sort_by === col) {
			sort_order = sort_order === "desc" ? "asc" : "desc";
		} else {
			sort_by = col;
			sort_order = "desc";
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

	function open_url(url) {
		if (url) window.open(url, "_blank");
	}

	function read_epoch_of(i) {
		return read_overrides.has(i.id) ? read_overrides.get(i.id) : i.read_epoch;
	}

	function open_and_mark_read(i) {
		open_url(i.url);
		if (!read_epoch_of(i)) {
			read_overrides.set(i.id, Math.floor(Date.now() / 1000));
			read_overrides = read_overrides;
			on_set_read(i, true);
		}
	}

	function toggle_read(i) {
		const new_read = !read_epoch_of(i);
		read_overrides.set(i.id, new_read ? Math.floor(Date.now() / 1000) : null);
		read_overrides = read_overrides;
		on_set_read(i, new_read);
	}

	function fmt_date(epoch) {
		if (!epoch) return "-";
		return new Date(epoch * 1000).toISOString().slice(0, 16).replace("T", " ");
	}

	// Reset scroll when items array reference changes.
	let prev_items_ref = null;
	$: if (items !== prev_items_ref) {
		prev_items_ref = items;
		reset_scroll();
	}

	svelte.onMount(() => {
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
</script>

<div class="border border-secondary rounded items-scroll" bind:this={scroll_el} on:scroll={on_scroll}>
	<table class="table table-sm table-dark mb-0">
		<thead>
			<tr>
				<th style="width:30px"></th>
				<th style="width:30px" title="read">✓</th>
				<th class="d-none d-sm-table-cell">type</th>
				<th>content</th>
				{#if show_username}
					<th class="d-none d-md-table-cell">user</th>
				{/if}
				<th class="d-none d-md-table-cell">sub</th>
				<th class="d-none d-lg-table-cell">categories</th>
				<th class="d-none d-sm-table-cell" style="cursor:pointer; user-select:none" on:click={() => toggle_sort("created")}>
					created{sort_by === "created" ? (sort_order === "desc" ? " ↓" : " ↑") : ""}
				</th>
				<th style="cursor:pointer; user-select:none" on:click={() => toggle_sort("saved")}>
					saved{sort_by === "saved" ? (sort_order === "desc" ? " ↓" : " ↑") : ""}
				</th>
			</tr>
		</thead>
		<tbody>
			{#if top_pad > 0}
				<tr aria-hidden="true"><td colspan={total_cols} style="padding:0; border:0"><div style="height:{top_pad}px"></div></td></tr>
			{/if}
			{#each window_rows as i (show_username ? `${i.username}::${i.id}` : i.id)}
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
							{i.type} · {i.sub}{#if show_username && i.username} · u/{i.username}{/if}{#if i.categories} · {i.categories}{/if}
						</div>
					</td>
					{#if show_username}
						<td class="d-none d-md-table-cell">u/{i.username}</td>
					{/if}
					<td class="d-none d-md-table-cell">{i.sub}</td>
					<td class="d-none d-lg-table-cell"><small>{i.categories}</small></td>
					<td class="d-none d-sm-table-cell"><small>{fmt_date(i.created_epoch)}</small></td>
					<td><small>{i.added_epoch ? fmt_date(i.added_epoch) : "-"}</small></td>
				</tr>
			{/each}
			{#if bot_pad > 0}
				<tr aria-hidden="true"><td colspan={total_cols} style="padding:0; border:0"><div style="height:{bot_pad}px"></div></td></tr>
			{/if}
			{#if visible_items.length === 0}
				<tr><td colspan={total_cols} class="text-muted text-center">no items</td></tr>
			{/if}
		</tbody>
	</table>
</div>

<style>
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
		.content-cell {
			max-width: 300px;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
	}
</style>
