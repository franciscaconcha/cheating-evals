# Yoto bedtime / morning via Hermes Agent

Message your Hermes agent on Telegram or WhatsApp ("bedtime", "morning",
"is the Yoto in night mode?") and it switches your Yoto player's day/night
mode on the spot.

`yoto_mcp.py` is a small MCP server that gives Hermes three tools:

| Tool | What it does |
| --- | --- |
| `yoto_bedtime` | Night mode now. Day mode returns at your usual morning time. |
| `yoto_morning` | Day mode now. Night mode returns at your usual bedtime. |
| `yoto_status` | Current mode, day/night times and volume limits per player. |

**How it works:** Yoto players switch modes at their `dayTime` and
`nightTime` settings. "Bedtime" sets `nightTime` to the next minute and
puts `dayTime` back to your usual morning time. "Morning" does the reverse.
Your normal schedule keeps working, and a manual switch only lasts until
the next scheduled change.

Night mode applies whatever night settings you already chose in the Yoto
app: volume limit, display brightness and night-light colour. Set those up
in the app first.

---

## 1. Prepare the droplet

Ubuntu 22.04/24.04 with at least 2 GB RAM is comfortable. The WhatsApp
bridge runs Node alongside Hermes.

Run Hermes as a normal user, not root:

```bash
ssh root@YOUR_DROPLET_IP
adduser hermes
usermod -aG sudo hermes
rsync -a ~/.ssh /home/hermes/ && chown -R hermes:hermes /home/hermes/.ssh
exit
ssh hermes@YOUR_DROPLET_IP
```

## 2. Install Hermes and choose a model

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
hermes setup          # pick a provider + model (Nous Portal, OpenRouter, OpenAI, ...)
hermes                # quick sanity chat in the terminal, then exit
```

## 3. Get a Yoto client ID

1. Sign in to the Yoto developer dashboard (linked from <https://yoto.dev>)
   with your Yoto account.
2. Create an app and copy its **Client ID**. The app must allow the
   **device code** sign-in flow. If the dashboard asks for an app type,
   pick the one for CLI, device or "public" clients.

## 4. Install the Yoto tool

Copy this `yoto-hermes` folder to the droplet. For example, from your laptop:

```bash
scp -r yoto-hermes hermes@YOUR_DROPLET_IP:~/
```

Then on the droplet:

```bash
sudo apt install -y python3-venv
cd ~/yoto-hermes
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 5. Sign in to Yoto and test (before involving Hermes)

```bash
export YOTO_CLIENT_ID=paste-your-client-id
export YOTO_TOKEN_FILE=$HOME/.config/yoto-hermes/token.json
.venv/bin/python yoto_mcp.py login     # open the link on your phone, approve
.venv/bin/python yoto_mcp.py status
.venv/bin/python yoto_mcp.py bedtime   # watch the player for up to ~1 minute
.venv/bin/python yoto_mcp.py morning
```

If you have several players, add `--player "Kids Room"` (any part of the
name) or `--player all`.

**Check the player itself.** Within about a minute it should change mode:
the night light changes and the volume is capped. If `status` shows the new
times but the player doesn't switch, the player may only apply the new
schedule at its next change-over. Let me know and the tool can also push
the night-light and volume change instantly over Yoto's MQTT channel.

## 6. Connect the tool to Hermes

Add your client ID to `~/.hermes/.env`:

```
YOTO_CLIENT_ID=paste-your-client-id
```

Add this to `~/.hermes/config.yaml`. Use absolute paths and change `hermes`
if your username differs:

```yaml
mcp_servers:
  yoto:
    command: /home/hermes/yoto-hermes/.venv/bin/python
    args: ["/home/hermes/yoto-hermes/yoto_mcp.py"]
    env:
      YOTO_CLIENT_ID: "${YOTO_CLIENT_ID}"
      YOTO_TOKEN_FILE: /home/hermes/.config/yoto-hermes/token.json
      YOTO_DAY_TIME: "07:00"        # your usual morning switch
      YOTO_NIGHT_TIME: "19:00"      # your usual bedtime switch
      # YOTO_PLAYER: "Kids Room"    # default player if you have several
      # YOTO_TIMEZONE: "Europe/London"  # only if the player's zone is wrong
```

Check it in the terminal: run `hermes`, then ask *"what Yoto tools do you
have?"* and *"what's the Yoto status?"*.

## 7. Telegram

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the token.
2. Message **@userinfobot** to get your numeric user ID. Add your partner's
   ID too if they should be able to use it.
3. Run `hermes gateway setup`, choose Telegram, and paste the token and
   IDs. Or put them in `~/.hermes/.env`:

   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_ALLOWED_USERS=123456789,987654321
   ```

## 8. WhatsApp (optional, alongside or instead of Telegram)

```bash
hermes whatsapp
```

Choose a mode:

- **bot**: the agent has its own WhatsApp number. Use a spare SIM or eSIM.
  This is the better choice.
- **self-chat**: you message yourself on your own number.

Scan the QR code with that WhatsApp account (**Settings → Linked devices**).
Make your SSH window at least 60 columns wide so the code renders. Then
check that `~/.hermes/.env` has:

```
WHATSAPP_ENABLED=true
WHATSAPP_MODE=bot
WHATSAPP_ALLOWED_USERS=15551234567     # country code, no +
```

WhatsApp unlinks devices after long inactivity. If that happens, run
`hermes whatsapp` again.

## 9. Run it 24/7

```bash
hermes gateway install               # systemd user service
sudo loginctl enable-linger $USER    # keep it running after you log out
hermes gateway start
hermes gateway status
```

Now message the bot: **"bedtime"**, **"morning"**, **"bedtime for all
players"**, **"is the Yoto in night mode?"**.

## Security notes

- **Keep the allowlists** (`TELEGRAM_ALLOWED_USERS`,
  `WHATSAPP_ALLOWED_USERS`). Never use `*` or `GATEWAY_ALLOW_ALL_USERS`.
  Hermes can run shell commands on the droplet.
- **Optional hardening:** if you only want this bot to handle the Yoto
  player, run `hermes tools` and switch off terminal, file and browser
  tools for the Telegram and WhatsApp platforms.
- **Protect the token file.** The Yoto sign-in is stored in
  `~/.config/yoto-hermes/token.json` with mode 600, and anyone with that
  file can change your player's settings. To revoke it, delete the file
  and remove the app's access in your Yoto account.
- **Firewall:** keep the droplet firewalled to SSH only. The gateway makes
  only outbound connections, so it needs no open ports.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Not signed in` / `sign-in expired` | Re-run step 5's `login`, using the same `YOTO_TOKEN_FILE` path as in config.yaml. |
| `Several players found` | Name the player in your message, or set `YOTO_PLAYER`. |
| Times are off by hours | Set `YOTO_TIMEZONE`. |
| Hermes doesn't see the tools | `hermes doctor`, check the paths in config.yaml, then restart: `hermes gateway stop && hermes gateway start`. |
| Device-code login rejected | The Yoto app's client type must allow the device code flow (step 3). |
