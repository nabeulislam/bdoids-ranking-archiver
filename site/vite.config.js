import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const contestsFile = resolve("src", "contests.json");
const contests = existsSync(contestsFile)
    ? JSON.parse(readFileSync(contestsFile, "utf8"))
    : [];

function archiveHtmlPlugin() {
    return {
        name: "patch-contest-html",
        transformIndexHtml(source, ctx) {
            const contest = contests.find((item) =>
                ctx.path.endsWith(`/${item.slug}/index.html`));
            if (!contest) return source;

            const title = contest.title || contest.label || contest.slug;
            const logo = contest.logo || "img/logo.png";
            const favicon = contest.favicon || "img/favicon.ico";

            return source
                .replaceAll("%YEAR%", title)
                .replaceAll("%YEAR_ID%", contest.slug)
                .replaceAll("%ARCHIVE_URL%", `/${contest.slug}/`)
                .replaceAll("%FAVICON%", favicon)
                .replaceAll("%LOGO%", logo);
        },
    };
}

export default defineConfig({
    appType: "mpa",
    base: "./",
    plugins: [archiveHtmlPlugin()],
    root: resolve("src"),
    publicDir: resolve("public"),
    resolve: { preserveSymlinks: true },
    build: {
        emptyOutDir: true,
        outDir: resolve("dist"),
        sourcemap: true,
        rollupOptions: {
            input: {
                main: resolve("src", "index.html"),
                "404": resolve("src", "404.html"),
                ...Object.fromEntries(
                    contests
                        .filter((c) => existsSync(resolve("src", c.slug, "index.html")))
                        .map((c) => [c.slug, resolve("src", c.slug, "index.html")])
                ),
            },
            output: {
                manualChunks: {
                    jquery: ["jquery"],
                    raphael: ["raphael"],
                },
            },
        },
    },
});

