# Doomsday — free ticket monitor

Monitors **Dec 18, 2026**, **Infinity Vision ICE 3D** sessions at **PVR Ambience Mall, Gurugram**, using a public theatre-specific TicketRadar listing. When the first target session appears, it sends a Telegram alert and **disables its own GitHub Actions workflow**.

**Cost guardrails:** Public GitHub repository + *standard* GitHub-hosted runner only (GitHub Actions is free for public repositories); free Telegram bot, no API subscriptions, no AWS, no credit card, no paid broadcast. The repository is public, **so do not store tokens or personal information in the files**. Never enable paid runners or choose a private repository without revisiting costs.

**Limitations:** TicketRadar may update later than BookMyShow or change layout; GitHub scheduled runs can be delayed or skipped. This detects *listed showtimes*, not proof that seats are bookable. It does not automatically book tickets. In particular, we have not verified that the external site is accessible from GitHub-hosted runners; manual testing is mandatory before relying on this.

## 1. Test on your Mac (using `uv`)

Open Terminal in this folder:

```bash
uv sync
uv run python ticket_watch.py check
uv run python -m unittest discover -s tests -v
```

There are no external Python dependencies. `uv sync` makes a local `.venv`; it doesn't modify system Python.

If the site rejects the check, **stop here**. The workflow would not reliably notify you.

## 2. Set up free Telegram notifications

1. Install Telegram on Android if needed.
2. In Telegram, open the verified [@BotFather](https://t.me/BotFather), send `/newbot`, and choose a name and username. It gives a **bot token**.
3. Open your newly created bot's chat and send `/start`.
4. **Locally on your Mac**, replace `<YOUR_BOT_TOKEN>` in the following URL and open it in a browser (don't share it with anyone):

   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`

   In the JSON response, find `"chat":{"id":123456789,...}`; that number is your **chat ID**. If result is empty, send the bot another message and refresh.
5. Test locally, without putting secrets in any file or GitHub commit:

```bash
export TELEGRAM_BOT_TOKEN='paste-your-token-here'
export TELEGRAM_CHAT_ID='paste-your-chat-id-here'
uv run python ticket_watch.py test-alert
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
```

This should send you one Telegram message. Tokens go only into your shell session and later GitHub **repository secrets**, never code.

## 3. Create a PUBLIC GitHub repository (₹0)

1. On GitHub, create a new **Public** repository, e.g. `doomsday-ticket-watch`. Don't initialize it with a README (this project already contains one). **Don't choose a private repo**, because the 5-minute schedule can consume paid metered Actions minutes once free allowances are exhausted.
2. In your Mac's terminal (inside this project directory), replace `YOUR_GITHUB_USERNAME`:

```bash
git init
git branch -M main
git add .
git commit -m 'Add free Doomsday ICE 3D monitor'
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/doomsday-ticket-watch.git
git push -u origin main
```

   GitHub may prompt you to log in/authenticate. Use their normal sign-in flow, not your Telegram token.
3. Go to **GitHub repo → Settings → Secrets and variables → Actions**. Add **repository secrets** (not public variables):

   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

4. Go to **Actions → Doomsday ticket monitor (free) → Run workflow**. Inspect the run output.
   - `Inspected N session(s); target ICE 3D matches: 0`: working; scheduled monitoring can continue.
   - `CHECK FAILED`: the monitor has sent an error message and disabled itself; investigate the source before enabling it again.
   - `target ICE 3D matches: 1` or more: alert delivered; workflow self-disables.

**Important:** Manual runs use the real source and can disable the workflow on match/error, just like scheduled ones. Re-enable it from the Actions page only after resolving errors.

## 4. Stopping and troubleshooting

In GitHub **Actions → Doomsday ticket monitor (free) → ... → Disable workflow**, you can stop it at any moment. The workflow automatically disables after matching an ICE 3D session or after the target date has passed (December 19 in India). An unexpected site error triggers a Telegram alert and disables monitoring instead of reporting a false negative.

If the GitHub-hosted runner gets a 403 or captcha, this monitor is **not a reliable cloud solution**; don't try to bypass the website's restrictions. Fall back to authorized notifications/manual booking checks. To verify whether scheduled runs are actually happening, view recent timestamps under the repo's Actions tab.

## 5. What is checked?

Source: https://ticketradar.in/f/avengers-doomsday/national-capital-region-ncr/theatre/paeg-gurugram-pepsi-pvr-ambience

BookMyShow booking page: https://in.bookmyshow.com/movies/national-capital-region-ncr/avengers-doomsday/ET00439706

The tool selects showtime rows with `Fri 18 Dec`, `ICE`, and `3D`. The source currently lists examples like `Thu 17 Dec ... MS InfVsn ICE 3D · ICE`.

The schedule is every five minutes (best effort); don't hammer the site. The script does not reserve or buy tickets, handle cookies/logins, or circumvent access controls.
