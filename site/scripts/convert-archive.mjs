import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const inputRoot = join(siteRoot, "archive-inputs");
const dataRoot = join(siteRoot, "src");
const publicRoot = join(siteRoot, "public");
const templatePath = join(dataRoot, "template", "index.html");
const contestsPath = join(dataRoot, "contests.json");

const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));

if (!existsSync(contestsPath)) {
    console.error(`Contests file not found: ${contestsPath}`);
    process.exit(1);
}

const contests = readJson(contestsPath);
const renderedContestItems = [];

for (const contest of contests) {
    const slug = contest.slug;
    const title = contest.title || contest.label || slug;

    // Resolve archive input directory
    let archiveRoot = join(inputRoot, contest.dir || slug);
    if (!existsSync(archiveRoot)) {
        archiveRoot = join(inputRoot, slug.replace(/^bdoids-/, ""));
    }
    if (!existsSync(archiveRoot)) {
        console.warn(`[warning] Skipping ${slug}: input directory '${archiveRoot}' not found`);
        continue;
    }

    const archiveDataRoot = join(dataRoot, slug);
    const archivePublicRoot = join(publicRoot, slug);

    // Ensure contest index.html exists from template
    const contestHtmlPath = join(archiveDataRoot, "index.html");
    if (!existsSync(contestHtmlPath)) {
        mkdirSync(archiveDataRoot, { recursive: true });
        if (existsSync(templatePath)) {
            cpSync(templatePath, contestHtmlPath);
        }
    }

    const data = {
        archive_title: title,
        contests: readJson(join(archiveRoot, "contests", "index.html")),
        tasks: readJson(join(archiveRoot, "tasks", "index.html")),
        teams: readJson(join(archiveRoot, "teams", "index.html")),
        users: readJson(join(archiveRoot, "users", "index.html")),
        scores: readJson(join(archiveRoot, "scores")),
        history: readJson(join(archiveRoot, "history")),
        asset_config: existsSync(join(archiveRoot, "asset_config"))
            ? readJson(join(archiveRoot, "asset_config"))
            : {},
        sublist: {},
    };

    const sublistDir = join(archiveRoot, "sublist");
    if (existsSync(sublistDir)) {
        for (const file of readdirSync(sublistDir)) {
            data.sublist[file] = readJson(join(sublistDir, file));
        }
    }

    mkdirSync(archiveDataRoot, { recursive: true });
    writeFileSync(join(archiveDataRoot, "data.json"), JSON.stringify(data));

    // Keep the original CMS archive endpoints alongside the bundled data.
    for (const directory of ["contests", "tasks", "teams", "users"]) {
        const sourceDir = join(archiveRoot, directory);
        if (existsSync(sourceDir)) {
            const outputDirectory = join(archivePublicRoot, directory);
            mkdirSync(outputDirectory, { recursive: true });
            if (existsSync(join(sourceDir, "index.html"))) {
                cpSync(join(sourceDir, "index.html"), join(outputDirectory, "index.html"));
            }
        }
    }

    for (const file of ["asset_config", "history", "scores", "logo"]) {
        const source = join(archiveRoot, file);
        if (existsSync(source)) {
            cpSync(source, join(archivePublicRoot, file));
        }
    }

    const facesSrc = join(archiveRoot, "faces");
    if (existsSync(facesSrc)) {
        const facesRoot = join(archivePublicRoot, "faces");
        mkdirSync(facesRoot, { recursive: true });
        for (const file of readdirSync(facesSrc)) {
            cpSync(join(facesSrc, file), join(facesRoot, file));
            cpSync(join(facesSrc, file), join(facesRoot, `${file}.png`));
        }
    }

    const flagsSrc = join(archiveRoot, "flags");
    if (existsSync(flagsSrc)) {
        const flagsRoot = join(archivePublicRoot, "flags");
        mkdirSync(flagsRoot, { recursive: true });
        for (const file of readdirSync(flagsSrc)) {
            cpSync(join(flagsSrc, file), join(flagsRoot, file));
        }
    }

    if (existsSync(sublistDir)) {
        const submissionsRoot = join(archivePublicRoot, "sublist");
        mkdirSync(submissionsRoot, { recursive: true });
        for (const file of readdirSync(sublistDir)) {
            cpSync(join(sublistDir, file), join(submissionsRoot, file));
        }
    }

    const archiveImgRoot = join(archivePublicRoot, "img");
    mkdirSync(archiveImgRoot, { recursive: true });
    const favSrc = join(archiveRoot, "img", "favicon.ico");
    if (existsSync(favSrc)) {
        cpSync(favSrc, join(archiveImgRoot, "favicon.ico"));
    }
    const logoSrc = join(archiveRoot, "img", "logo.png");
    if (existsSync(logoSrc)) {
        cpSync(logoSrc, join(archiveImgRoot, "logo.png"));
    }

    renderedContestItems.push(`        <li><a href="${slug}/">${title}</a></li>`);
    console.log(`Wrote ${join(archiveDataRoot, "data.json")}`);
}

const flagsRoot = join(publicRoot, "flags-c76d8b51cddaf48f");
mkdirSync(flagsRoot, { recursive: true });
for (const contest of contests) {
    let archiveRoot = join(inputRoot, contest.dir || contest.slug);
    if (!existsSync(archiveRoot)) {
        archiveRoot = join(inputRoot, contest.slug.replace(/^bdoids-/, ""));
    }
    const flagsSrc = join(archiveRoot, "flags");
    if (existsSync(flagsSrc)) {
        for (const file of readdirSync(flagsSrc)) {
            cpSync(join(flagsSrc, file), join(flagsRoot, `${file}.png`));
        }
    }
}

const defaultFavicon = join(publicRoot, contests[0]?.slug || "", "img", "favicon.ico");
if (existsSync(defaultFavicon)) {
    cpSync(defaultFavicon, join(publicRoot, "favicon.ico"));
}

const sharedImgRoot = join(publicRoot, "img");
mkdirSync(sharedImgRoot, { recursive: true });
const srcImg = join(dataRoot, "img");
if (existsSync(srcImg)) {
    for (const file of readdirSync(srcImg)) {
        cpSync(join(srcImg, file), join(sharedImgRoot, file));
    }
}

const publicLibRoot = join(publicRoot, "lib");
mkdirSync(publicLibRoot, { recursive: true });
const srcLib = join(dataRoot, "public", "lib");
if (existsSync(srcLib)) {
    for (const file of readdirSync(srcLib)) {
        cpSync(join(srcLib, file), join(publicLibRoot, file));
    }
}

// Update landing page contest list
const indexPath = join(dataRoot, "index.html");
if (existsSync(indexPath) && renderedContestItems.length > 0) {
    let indexHtml = readFileSync(indexPath, "utf8");
    const startTag = "<!-- CONTEST_LIST_START -->";
    const endTag = "<!-- CONTEST_LIST_END -->";
    const startIdx = indexHtml.indexOf(startTag);
    const endIdx = indexHtml.indexOf(endTag);
    if (startIdx !== -1 && endIdx !== -1) {
        const replacement = `${startTag}\n    <ul>\n${renderedContestItems.join("\n")}\n    </ul>\n    ${endTag}`;
        indexHtml = indexHtml.slice(0, startIdx) + replacement + indexHtml.slice(endIdx + endTag.length);
        writeFileSync(indexPath, indexHtml);
    }
}

