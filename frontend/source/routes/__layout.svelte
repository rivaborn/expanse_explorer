<script context="module">
	import * as globals from "frontend/source/globals.js";
	import { page } from "$app/stores";
	const globals_r = globals.readonly;
</script>

<div class="container-fluid p-3">
	<nav class="mb-3 d-flex flex-wrap align-items-center" style="gap:1rem">
		<a href="/" class:nav-active={$page.url.pathname === "/"}>browse by category</a>
		<a href="/by_user" class:nav-active={$page.url.pathname === "/by_user"}>browse by user</a>
		<a href="/topics" class:nav-active={$page.url.pathname === "/topics" || $page.url.pathname.startsWith("/topics/")}>organize by category</a>
	</nav>
	<slot></slot>
</div>

<style>
	nav a {
		color: #aaa;
		text-decoration: none;
		font-size: 0.95rem;
		padding-bottom: 2px;
		border-bottom: 2px solid transparent;
	}
	nav a:hover {
		color: #fff;
		text-decoration: none;
	}
	nav a.nav-active {
		color: #fff;
		border-bottom-color: #fff;
	}
</style>
