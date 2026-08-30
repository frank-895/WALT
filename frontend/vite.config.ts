import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
	const environment = loadEnv(mode, ".", "WALT_");

	return {
		plugins: [react()],
		server: {
			host: "0.0.0.0",
			proxy: {
				"/api": environment.WALT_BACKEND_URL ?? "http://localhost:8000",
			},
		},
	};
});
