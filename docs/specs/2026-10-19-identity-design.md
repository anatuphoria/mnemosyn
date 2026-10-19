# The ΜΝΗΜΟΣΥΝΗ identity and a cleaner README

Date: 2026-10-19
Status: chosen by the owner from mockups on 2026-10-19; awaiting the owner's review of this text
Branch: `identity`

## 1. Why

The Greek name ΜΝΗΜΟΣΥΝΗ, in the website's spaced classical serif (GFS Didot), is what the owner
likes most about the project's look. It becomes the identity of everything: the README, the
website, the app, the installer and the AppImage. The README, written before the website existed,
repeats much of what the website now says; it should become a clean front page that still tells a
GitHub visitor what Mnemosyn is and how to get it, and sends them to the website for the details.

## 2. The logo (owner's choice: "A. Inscription")

- **Wordmark:** ΜΝΗΜΟΣΥΝΗ in GFS Didot, widely spaced like letters cut in stone, between two thin
  blue rules (#3d6fd6) above and below, on the app's dark ink (#16161d) or transparent.
- **Mark:** a single Μ between the same two rules, in a rounded dark square, for the app icon,
  the installer, the AppImage, the website's logo and favicon.
- The letters are turned into outlines, so the logo looks the same where the font is not
  installed (GitHub, the app, any viewer). GFS Didot is under the SIL Open Font Licence, which
  allows this; its licence text is kept next to the logo files.
- Light and dark versions of the wordmark (dark ink letters for light backgrounds, light letters
  for dark ones); the README uses GitHub's light/dark picture switch so it reads in both themes.

## 3. Badges (owner's choice: our own)

Badges are our own small pictures in the same style: a spaced Didot label in grey and its value in
light ink, between two thin rules on dark ink. Release (version and "test"), licence (GPL 3.0),
platforms (Windows · Linux), website, and review (open to specialists, with gold rules like the
website's disclaimer). Each links where it should (release page, licence, Download page, website,
Review page). A script redraws them, with the logo and icons, from `pyproject.toml`'s version; the
release instructions gain that one step.

## 4. The README (owner: "clean it, don't remove necessary things")

Order: logo and one-line tagline; badges; quick links into the website (Download, Using the app,
The atlas, Review, Decisions); one real screenshot of the app (3D view with a pathway and slices);
"What it is" (a short paragraph and the main features in a few bullets); "Get it" (download link,
and a short build-from-source block with the commands); "The atlas data" (a short summary with
the sources table or a link to the website's sources page, keeping the licence facts); "Review and
disclaimer"; "Contributing and licence"; and links to the website for everything detailed (keys,
panels, quizzes, routes, performance limits, build rules, packaging, design documents). Nothing
that a GitHub visitor needs is removed; detail moves, it is not lost.

## 5. The website keeps everything

The website today builds three pages from README sections (Using the app from "Desktop app",
Performance from "Performance", and Download's "Build from source" from "Quickstart"). Their
current text moves into the website's own source files first, so no page loses content when the
README is cleaned. The website's header logo and favicon become the inscription mark; the home
page's existing Greek title and layout stay as they are (owner likes them).

## 6. The app

The window and taskbar icon, the installer and the AppImage use the Μ mark. The About box opens
with the inscription wordmark above the version. Builder's call: whether the window title shows
the Greek name (it stays "Mnemosyn" unless that looks right in practice).

## 7. Out of scope

New features; colour changes beyond the existing ink and blue; translating any text into Greek.

## 8. Decisions to log

The ΜΝΗΜΟΣΥΝΗ inscription as the project's identity (logo, mark, badges), and the README as a
clean front page with the website as the full documentation.
