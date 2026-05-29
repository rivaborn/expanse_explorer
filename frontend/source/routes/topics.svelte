<script context="module">
	import * as globals from "frontend/source/globals.js";
	import * as svelte from "svelte";
	import axios from "axios";
	const globals_r = globals.readonly;
</script>
<script>
	let topics = [];
	let subs = [];
	let selected_sub_set = new Set();
	let target_topic = null;
	let filter_topic = "__none__"; // "__none__" | "__all__" | <topic-name>
	let new_topic_name = "";
	let renaming = null;          // topic name currently being renamed
	let rename_text = "";
	let status_message = "";
	let is_loading = false;
	let sort_by_count = false;    // subreddit + topic list sort

	$: sorted_subs = sort_by_count
		? [...subs].sort((a, b) => b.item_count - a.item_count || a.sub.localeCompare(b.sub))
		: [...subs].sort((a, b) => a.sub.localeCompare(b.sub));

	$: sorted_topics = sort_by_count
		? [...topics].sort((a, b) => b.item_count - a.item_count || a.topic.localeCompare(b.topic))
		: [...topics].sort((a, b) => a.topic.localeCompare(b.topic));

	$: assignable = target_topic && selected_sub_set.size > 0 && !is_loading;
	$: unassignable = selected_sub_set.size > 0 && !is_loading;

	async function load_topics() {
		try {
			const r = await axios.get(`${globals_r.backend}/api/topics`);
			topics = r.data.topics || [];
		} catch (err) {
			console.error(err);
			status_message = `error loading topics: ${err.message}`;
		}
	}

	async function load_subs() {
		try {
			const params = {};
			if (filter_topic !== "__all__") params.topic = filter_topic;
			const r = await axios.get(`${globals_r.backend}/api/all_subs`, { params });
			subs = r.data.subs || [];
			selected_sub_set = new Set();
		} catch (err) {
			console.error(err);
			status_message = `error loading subs: ${err.message}`;
		}
	}

	async function refresh_all() {
		await load_topics();
		await load_subs();
	}

	function on_filter_change() {
		load_subs();
	}

	function toggle_sub(name) {
		if (selected_sub_set.has(name)) selected_sub_set.delete(name);
		else selected_sub_set.add(name);
		selected_sub_set = selected_sub_set;
	}

	function toggle_all_subs() {
		if (selected_sub_set.size === subs.length) {
			selected_sub_set = new Set();
		} else {
			selected_sub_set = new Set(subs.map(s => s.sub));
		}
	}

	async function add_topic() {
		const name = new_topic_name.trim();
		if (!name) return;
		is_loading = true;
		status_message = "";
		try {
			await axios.post(`${globals_r.backend}/api/topics`, { topic: name });
			new_topic_name = "";
			status_message = `added "${name}"`;
			await load_topics();
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	function start_rename(topic) {
		renaming = topic;
		rename_text = topic;
	}

	function cancel_rename() {
		renaming = null;
		rename_text = "";
	}

	async function commit_rename() {
		const old_name = renaming;
		const new_name = rename_text.trim();
		if (!old_name || !new_name || old_name === new_name) {
			cancel_rename();
			return;
		}
		is_loading = true;
		status_message = "";
		try {
			await axios.patch(`${globals_r.backend}/api/topics`, { old: old_name, new: new_name });
			status_message = `renamed "${old_name}" → "${new_name}"`;
			cancel_rename();
			if (target_topic === old_name) target_topic = new_name;
			if (filter_topic === old_name) filter_topic = new_name;
			await refresh_all();
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	async function delete_topic(topic) {
		const t = topics.find(x => x.topic === topic);
		const sub_count = t ? t.sub_count : 0;
		const msg = sub_count > 0
			? `Delete "${topic}"? This will unmap ${sub_count} subreddit${sub_count === 1 ? "" : "s"} back to Uncategorized.`
			: `Delete "${topic}"?`;
		if (!window.confirm(msg)) return;
		is_loading = true;
		status_message = "";
		try {
			const r = await axios.delete(`${globals_r.backend}/api/topics/${encodeURIComponent(topic)}`);
			status_message = `deleted "${topic}" (unmapped ${r.data.cascaded_sub_topic_rows} subs)`;
			if (target_topic === topic) target_topic = null;
			if (filter_topic === topic) filter_topic = "__none__";
			await refresh_all();
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	async function apply_assign(topic_or_null) {
		if (selected_sub_set.size === 0) return;
		if (topic_or_null && !topics.some(t => t.topic === topic_or_null)) {
			status_message = `unknown topic: ${topic_or_null}`;
			return;
		}
		is_loading = true;
		status_message = "";
		try {
			const r = await axios.post(`${globals_r.backend}/api/assign_topic`, {
				subs: Array.from(selected_sub_set),
				topic: topic_or_null
			});
			status_message = topic_or_null
				? `assigned ${r.data.assigned_count} sub${r.data.assigned_count === 1 ? "" : "s"} → "${topic_or_null}"`
				: `unassigned ${r.data.assigned_count} sub${r.data.assigned_count === 1 ? "" : "s"}`;
			await refresh_all();
		} catch (err) {
			console.error(err);
			status_message = `error: ${err.response?.data?.error || err.message}`;
		} finally {
			is_loading = false;
		}
	}

	svelte.onMount(() => {
		refresh_all();
	});

	function filter_label(value) {
		if (value === "__none__") return "Uncategorized";
		if (value === "__all__") return "All";
		return value;
	}
</script>

<svelte:head>
	<title>organize by category · {globals_r.app_name}</title>
</svelte:head>

<div class="d-flex flex-wrap justify-content-between align-items-center mb-3" style="gap:0.5rem">
	<h3 class="m-0">organize by category</h3>
	<small class="text-muted">{topics.length} topics · {subs.length} subs in filter</small>
</div>

{#if status_message}
	<div class="alert alert-info py-1 px-2">{status_message}</div>
{/if}

<section class="card bg-dark border-secondary mb-3">
	<div class="card-body py-2">
		<h6 class="card-title mb-2">manage categories</h6>
		<div class="d-flex flex-wrap align-items-center mb-2" style="gap:0.5rem">
			<input
				bind:value={new_topic_name}
				type="text"
				placeholder="new category name"
				class="form-control form-control-sm bg-dark text-light border-secondary"
				style="max-width:300px; flex:1 1 200px"
				on:keydown={(e) => e.key === "Enter" && add_topic()}/>
			<button class="btn btn-sm btn-primary" on:click={add_topic} disabled={is_loading || !new_topic_name.trim()}>add</button>
		</div>
		<div class="topics-grid">
			{#each sorted_topics as t (t.topic)}
				<div class="d-flex align-items-center topic-row" style="gap:0.5rem">
					{#if renaming === t.topic}
						<input
							bind:value={rename_text}
							type="text"
							class="form-control form-control-sm bg-dark text-light border-secondary"
							style="max-width:240px; flex:1 1 180px"
							on:keydown={(e) => {
								if (e.key === "Enter") commit_rename();
								if (e.key === "Escape") cancel_rename();
							}}/>
						<button class="btn btn-sm btn-success" on:click={commit_rename} disabled={is_loading}>save</button>
						<button class="btn btn-sm btn-outline-light" on:click={cancel_rename} disabled={is_loading}>cancel</button>
					{:else}
						<a href={`/topics/${encodeURIComponent(t.topic)}`} class="topic-link" title="browse items in this category">{t.topic}</a>
						<small class="text-muted">{t.sub_count} subs · {t.item_count} items</small>
						<button class="btn btn-sm btn-outline-light ml-auto" on:click={() => start_rename(t.topic)} disabled={is_loading}>rename</button>
						<button class="btn btn-sm btn-outline-danger" on:click={() => delete_topic(t.topic)} disabled={is_loading}>delete</button>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</section>

<section class="card bg-dark border-secondary">
	<div class="card-body py-2">
		<h6 class="card-title mb-2">categorize subreddits</h6>
		<div class="d-flex flex-wrap align-items-center mb-2" style="gap:0.5rem">
			<label class="mb-0 small">showing:</label>
			<select
				bind:value={filter_topic}
				on:change={on_filter_change}
				class="form-control form-control-sm bg-dark text-light border-secondary"
				style="max-width:300px; flex:1 1 200px">
				<option value="__none__">Uncategorized</option>
				<option value="__all__">All</option>
				{#each sorted_topics as t (t.topic)}
					<option value={t.topic}>{t.topic} ({t.sub_count})</option>
				{/each}
			</select>
			<label class="mb-0 small ml-3">
				<input type="checkbox" bind:checked={sort_by_count}/>
				sort by count
			</label>
		</div>

		<div class="row">
			<div class="col-12 col-md-7 mb-3 mb-md-0">
				<div class="d-flex align-items-center mb-2" style="gap:0.5rem">
					<b class="small">subreddits in {filter_label(filter_topic)}</b>
					<button class="btn btn-sm btn-outline-light" on:click={toggle_all_subs} disabled={subs.length === 0}>
						{selected_sub_set.size === subs.length && subs.length > 0 ? "deselect all" : "select all"}
					</button>
					<small class="text-muted">{selected_sub_set.size} selected of {subs.length}</small>
				</div>
				<div class="sub-list border border-secondary rounded">
					{#each sorted_subs as s (s.sub)}
						<label class="d-flex align-items-center sub-row py-1 px-2 mb-0">
							<input type="checkbox" checked={selected_sub_set.has(s.sub)} on:change={() => toggle_sub(s.sub)} class="mr-2"/>
							<span class="flex-fill">{s.sub}</span>
							{#if s.topic && filter_topic === "__all__"}<small class="text-info mr-2">{s.topic}</small>{/if}
							<small class="text-muted">{s.item_count}</small>
						</label>
					{/each}
					{#if subs.length === 0}
						<div class="text-muted small p-2">no subreddits in this filter</div>
					{/if}
				</div>
			</div>

			<div class="col-12 col-md-5">
				<div class="mb-2"><b class="small">target category</b></div>
				<div class="topic-list border border-secondary rounded">
					{#each sorted_topics as t (t.topic)}
						<label class="d-flex align-items-center topic-radio py-1 px-2 mb-0">
							<input type="radio" name="target_topic" value={t.topic} bind:group={target_topic} class="mr-2"/>
							<span class="flex-fill">{t.topic}</span>
							<small class="text-muted">{t.sub_count}</small>
						</label>
					{/each}
				</div>
				<div class="mt-3 d-flex flex-wrap" style="gap:0.5rem">
					<button class="btn btn-sm btn-warning" on:click={() => apply_assign(target_topic)} disabled={!assignable}>
						assign{target_topic ? ` → ${target_topic}` : ""}
					</button>
					<button class="btn btn-sm btn-outline-danger" on:click={() => apply_assign(null)} disabled={!unassignable}>unassign</button>
				</div>
			</div>
		</div>
	</div>
</section>

<style>
	.topics-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.25rem;
	}
	@media (min-width: 768px) {
		.topics-grid {
			grid-template-columns: 1fr 1fr;
		}
	}
	.topic-row {
		padding: 2px 4px;
		border-bottom: 1px solid #333;
	}
	.topic-link {
		color: #fff;
		text-decoration: underline;
		text-decoration-color: rgba(255, 255, 255, 0.3);
	}
	.topic-link:hover {
		color: #fff;
		text-decoration-color: rgba(255, 255, 255, 0.8);
	}
	.sub-list,
	.topic-list {
		max-height: 50vh;
		overflow-y: auto;
		background-color: #1a1a1a;
	}
	.sub-row,
	.topic-radio {
		cursor: pointer;
		border-bottom: 1px solid #2a2a2a;
	}
	.sub-row:hover,
	.topic-radio:hover {
		background-color: #2a2a2a;
	}
</style>
