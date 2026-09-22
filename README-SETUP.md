# Experiment Events HQ — public link on Hostinger

One file (`index.html`), one free database (Firebase). About 10 minutes total.

## Step 1 — Create the free database (Firebase)

1. Go to https://console.firebase.google.com and sign in with any Google account.
2. **Add project** → name it `experiment-hq` → you can turn OFF Google Analytics → Create.
3. In the left menu: **Build → Firestore Database → Create database** → choose a region close to Oman (e.g. `eur3` or `me-central`) → **Start in production mode** → Enable.
4. Open the **Rules** tab, replace everything with the rules below, and click **Publish**:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if true;
    }
  }
}
```

5. Click the ⚙️ gear (top left) → **Project settings** → scroll to **Your apps** → click the **`</>` (Web)** icon → nickname `hq` → Register app. Firebase shows a `firebaseConfig` block.

## Step 2 — Put the config into index.html

Open `index.html` in any text editor and find this block near the top of the `<script>`:

```js
const CONFIG={
  firebase:{
    apiKey:"",
    authDomain:"",
    projectId:""
  },
  accessCode:""
};
```

Copy `apiKey`, `authDomain` and `projectId` from the Firebase config into it.

**Strongly recommended:** set `accessCode:"something-your-team-knows"`. The page will ask for it once per device. (See "Security" below.)

## Step 3 — Upload to Hostinger

1. Log in to **hPanel** → your website → **Files → File Manager**.
2. Open `public_html` (or create a folder like `public_html/office`).
3. **Upload** `index.html` there.
4. Your live office is now at `https://yourdomain.com/` (or `https://yourdomain.com/office/`).

Put that URL on the office TV and share it with the team. Everything works exactly like before: check-in, walking, action items, chat, and the projects rail.

## Step 4 — Load the projects (one click)

The first person to open the configured page sees an **"Import tracker (146)"** button at the top of the Projects rail — click it once. It loads all 146 projects from the Tracker EXP pipeline (statuses, deadlines, leads, notes). After that the button disappears.

## Differences from the claude.ai version

- Identity is the "Who are you?" picker (remembered per device) — no claude.ai account needed.
- The "other visitors walking live" layer is off in this version; check-in status, chat and projects are all still live for everyone.

## Security — read this once

The page is a single file with an open database, protected only by the access code prompt. That's fine for an internal team board with no sensitive data, but anyone determined who has the link **and** opens the browser console could read or write the data. Don't put anything confidential in chat or notes. If you later want real logins (email/password per employee), that's a small upgrade — ask Claude to add Firebase Authentication and per-user rules.

## Updating the page later

The design lives in `index.html`. To change the office image, roster, or anything else, ask Claude for a new `index.html` and re-upload it — the data in Firebase is untouched by page updates.
