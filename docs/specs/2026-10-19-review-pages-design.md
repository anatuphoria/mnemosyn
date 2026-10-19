# Review pages on the website

Date: 2026-10-19
Status: approved by the owner on 2026-10-19; built on `main`
Branch: `main` (a small project before packaging, sub-project F)

## 1. Why

Mnemosyn is open source and asks specialists to check its anatomy and clinical texts. The review
material exists (a booklet with editions, a Google Form for answers, a consent and credit choice),
but nobody can find it: it lives in the untracked `review/` folder and reaches reviewers only by
email. The website should say that a review is open, let anyone download the booklet, and let a
specialist ask for access to the answer form.

## 2. How a specialist takes part (decided by the owner)

1. They open the **Review** page, read what the review is and download the booklet PDF.
2. On the same page they fill in a short **access request** form: full name, email address,
   speciality, institution (optional), the date from which they want access, and consent to be
   contacted about the review.
3. Each request reaches the owner by email and is also kept in a Google Sheet.
4. The owner replies by email with the link to the review form, on or before the asked date. The
   review form link is never published on the website.

No account, server or automation beyond Google Forms; the owner approves every request by hand.

## 3. Pages

- **Review** (new, in the navigation): what is being reviewed and why, who it is for, the four
  steps above, the booklet download (latest edition), the embedded request form, and a privacy
  note: what the request form keeps (the fields above), where (a private Google Sheet owned by
  the project), why (to send the review link and keep in touch about the review), for how long
  (until the review ends or the person asks), and how to ask for deletion (by email to the
  owner's address).
- **Booklet editions** (a section of the Review page): every edition with its date and a short
  "what changed", and a download for the latest. Old editions are listed, not offered.
- **Reviewers** (new page): reviewers and contributors who chose to be credited, with the name as
  they asked it to appear and, if they chose, their institution. Nobody is listed without that
  choice. Until there are names, the page says the list starts when the first reviews are in.
- **Home page:** the existing layout stays exactly as it is (owner's wish). The disclaimer at the
  bottom, which already says the atlas was not reviewed by a specialist, gains one sentence:
  "Are you a specialist? Help us review it", linking to the Review page.

## 4. Data and files

- The booklet PDF goes into the repository (owner's choice, 2026-10-19; only the PDF, the rest of
  `review/` stays out of git) under the site's files, named by edition. It shows the owner's Gmail
  as the contact (owner's choice).
- The request form is made by a Google Apps Script kept with the review form script in
  `review/form/` (not committed), which the owner runs once, as for the review form. It creates the
  form and its answer sheet, and sends the owner an email for each new request with the answers in
  it. Its link goes into a small committed file the site build reads, together with the list of
  editions and the list of credited reviewers. Until the link is filled in, the Review page says
  requests open soon and gives the owner's email instead.
- The credited reviewers list is kept by hand by the owner in that file (the site cannot and must
  not read the private answer sheet).

## 5. Out of scope

- The Download page for installers (packaging, sub-project F); the Install page stays as it is.
- Sending the second edition to the existing reviewers (the owner, with the drafted email).
- Any change to the review form or its 50 questions.

## 6. Decisions to log

The booklet PDF is published on the website (changing "`review/` is never committed" for that one
file), access to the review form is by request and the owner's reply, and credited reviewers are
listed only with their consent.
