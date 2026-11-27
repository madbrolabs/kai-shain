#!/bin/bash
# 借りたサーバー（Ubuntu 24.04）に社員ページの門番を入れる（何度流しても同じ結果）。root で流す。
#   使い方：git clone https://github.com/madbrolabs/kai-shain.git /srv/kai_shain
#           sudo bash /srv/kai_shain/hikkoshi/setup.sh kailab.co.jp
#   ドメインを渡さない時は、門番だけ入れて Caddy（入口）は触らない。
#   KAI_UFW=1 を付けると、外から開ける口を 80・443・22（ssh）と tailscale だけにする。
# データ（内緒の場所）はこれでは作らない。手順.md 3〜4 で PC から送る。送る前は門番を起こさない。
set -euo pipefail

DOMAIN="${1:-}"
REPO=/srv/kai_shain
NAISHO=/srv/kai_shain_private
VENV=/srv/kai_shain_venv
HERE="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" = 0 ] || { echo "root で流してください（sudo bash $0 ...）"; exit 1; }
[ "$HERE" = "$REPO/hikkoshi" ] || { echo "倉庫は $REPO に置いてください（今は $HERE）"; exit 1; }
if [ -n "$DOMAIN" ] && ! [[ "$DOMAIN" =~ ^[a-z0-9.-]+\.[a-z]{2,}$ ]]; then
  echo "ドメインの形が違います：$DOMAIN"; exit 1
fi

# 1 道具
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv rsync git gh curl caddy
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh

# 2 門番を動かす人（ログインできない）と置き場
id kai >/dev/null 2>&1 || useradd -r -M -d "$NAISHO/home" -s /usr/sbin/nologin kai
install -d -m 700 -o kai -g kai "$NAISHO" "$NAISHO/home" "$NAISHO/meibo"
install -d -m 700 -o kai -g kai "$NAISHO/secret"
# PC にしか無い物を指す「無い場所」（kai_mon.service の KAI_CC_SESSIONS など）。中は空のまま
install -d -m 700 -o kai -g kai "$NAISHO/nai"

# 3 コードは root の物（門番からは書き換えられない）。Python の部品
chown -R root:root "$REPO"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$REPO/hikkoshi/requirements.txt"

# 4 GitHub の鍵の置き方（中身は手順.md 4 で PC から画面に出さずに送る）
sudo -u kai env HOME="$NAISHO/home" git config --global credential.helper store

# 5 門番を常に動かす
sed "s/<ドメイン>/${DOMAIN:-example.invalid}/g" "$REPO/hikkoshi/kai_mon.service" > /etc/systemd/system/kai_mon.service
systemctl daemon-reload
systemctl enable kai_mon >/dev/null
if [ -f "$NAISHO/secret/mon.json" ]; then
  systemctl restart kai_mon
  echo "門番を起こしました（systemctl status kai_mon）"
else
  echo "まだデータがありません。手順.md 3〜4 で送ってから：systemctl start kai_mon"
fi

# 6 ログを週ごとに回す（8週分）
cat > /etc/logrotate.d/kai_shain <<EOF
$NAISHO/*.log $NAISHO/kamei/*.log {
  weekly
  rotate 8
  compress
  missingok
  notifempty
  copytruncate
  su kai kai
}
EOF

# 7 入口（Caddy）。ほかのソフトの塊は消さない＝自分の分だけ sites/ に置き、import を1行足す
if [ -n "$DOMAIN" ]; then
  install -d /etc/caddy/sites
  sed "s/<ドメイン>/$DOMAIN/g" "$REPO/hikkoshi/Caddyfile" > /etc/caddy/sites/kai_shain.caddy
  grep -qx 'import sites/\*.caddy' /etc/caddy/Caddyfile || printf '\nimport sites/*.caddy\n' >> /etc/caddy/Caddyfile
  caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile
  systemctl reload caddy
  echo "入口：https://shain.$DOMAIN/kai/ （DNS の shain.$DOMAIN をこのサーバーの番地に向けてから）"
else
  echo "ドメインを渡していないので、Caddy は触っていません"
fi

# 8 （望む時だけ）外から開ける口をしぼる
if [ "${KAI_UFW:-0}" = 1 ]; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow in on tailscale0
  ufw --force enable
fi

echo "次：tailscale up --ssh --hostname=kai-server （社長のアカウントで入る・手順.md 2）"
