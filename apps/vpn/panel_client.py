import os
import uuid
import time
import json
import requests
import paramiko
import base64

PANEL_URL     = os.getenv("PANEL_URL")
PANEL_PATH    = os.getenv("PANEL_PATH", "/")
PANEL_USER    = os.getenv("PANEL_USER")
PANEL_PASS    = os.getenv("PANEL_PASS")
INBOUND_ID    = int(os.getenv("PANEL_INBOUND_ID", "1"))

DE_IP         = os.getenv("DE_SERVER_IP")
DE_PORT       = os.getenv("DE_SERVER_PORT", "443")
DE_PUBLIC_KEY = os.getenv("DE_PUBLIC_KEY")
DE_SHORT_ID   = os.getenv("DE_SHORT_ID", "47")
DE_SNI        = os.getenv("DE_SNI", "yahoo.com")

RU_IP         = os.getenv("RU_SERVER_IP")
RU_PORT       = os.getenv("RU_SERVER_PORT", "443")
RU_UUID       = os.getenv("RU_UUID")
RU_PUBLIC_KEY = os.getenv("RU_PUBLIC_KEY")
RU_SHORT_ID   = os.getenv("RU_SHORT_ID", "f1")
RU_SNI        = os.getenv("RU_SNI", "yahoo.com")

DE_SSH_HOST   = os.getenv("DE_SSH_HOST")
DE_SSH_PORT   = int(os.getenv("DE_SSH_PORT", "22"))
DE_SSH_USER   = os.getenv("DE_SSH_USER", "root")
DE_SSH_KEY    = os.getenv("DE_SSH_KEY_PATH")
SUB_DIR       = os.getenv("SUB_DIR", "/var/www/sub")
SUB_BASE_URL  = os.getenv("SUB_BASE_URL")

class PanelClient:
    """
    Клиент для работы с 3x-ui API и генерации подписок.
    Основной метод: create_subscription()
    """

    # ── 3x-ui API ─────────────────────────────────────────────────

    def _get_session(self) -> requests.Session:
        """Авторизуется в панели и возвращает сессию с куками."""
        session = requests.Session()
        session.verify = False
        resp = session.post(
            f"{PANEL_URL}{PANEL_PATH}login",
            json={"username": PANEL_USER, "password": PANEL_PASS},
            timeout=10
        )
        data = resp.json()
        if not data.get("success"):
            raise Exception(f"Panel login failed: {data}")
        return session

    def create_panel_client(self, email: str, days: int) -> dict:
        """
        Создаёт клиента в 3x-ui inbound.

        Параметры:
            email: уникальный идентификатор, например "u123456789_42"
            days:  срок действия в днях

        Возвращает:
            {
                "uuid":   "UUID клиента — используется в DE ключе",
                "sub_id": "SubID — используется как имя файла подписки"
            }

        Запрос к 3x-ui API:
            POST /panel/inbound/addClient
            Body: {
                "id": 1,                        ← PANEL_INBOUND_ID
                "settings": "{\"clients\":[{    ← JSON-строка (не объект!)
                    \"id\": \"UUID\",
                    \"email\": \"u123_1\",
                    \"expiryTime\": 1234567890000,
                    \"subId\": \"abc123\",
                    \"enable\": true,
                    \"flow\": \"xtls-rprx-vision\",
                    \"limitIp\": 3,
                    \"totalGB\": 0
                }]}"
            }
        """
        client_uuid = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex[:16]
        exp_ms = (int(time.time()) + days * 86400) * 1000

        client_data = {
            "id":         client_uuid,
            "email":      email,
            "expiryTime": exp_ms,
            "subId":      sub_id,
            "enable":     True,
            "flow":       "xtls-rprx-vision",
            "limitIp":    3,
            "totalGB":    0,
        }

        session = self._get_session()
        resp = session.post(
            f"{PANEL_URL}{PANEL_PATH}panel/api/inbounds/addClient",
            json={
                "id": INBOUND_ID,
                "settings": json.dumps({"clients": [client_data]})
            },
            timeout=10
        )
        data = resp.json()
        if not data.get("success"):
            raise Exception(f"addClient failed: {data}")

        return {"uuid": client_uuid, "sub_id": sub_id}

    def delete_panel_client(self, client_uuid: str) -> bool:
        """
        Удаляет клиента из inbound.
        URL: POST /panel/inbound/{inbound_id}/delClient/{uuid}
        """
        session = self._get_session()
        resp = session.post(
            f"{PANEL_URL}{PANEL_PATH}panel/api/inbounds/{INBOUND_ID}/delClient/{client_uuid}",
            timeout=10
        )
        return resp.json().get("success", False)

    def update_panel_client(self, email: str,
                             client_uuid: str, days: int) -> bool:
        """
        Продлевает срок действия клиента в 3x-ui.
        URL: POST /panel/inbound/updateClient/{uuid}
        """
        exp_ms  = (int(time.time()) + days * 86400) * 1000
        session = self._get_session()
        resp = session.post(
            f"{PANEL_URL}{PANEL_PATH}panel/api/inbounds/updateClient/{client_uuid}",
            json={
                "id": INBOUND_ID,
                "settings": json.dumps({"clients": [{
                    "id":         client_uuid,
                    "email":      email,
                    "expiryTime": exp_ms,
                    "enable":     True,
                    "flow":       "xtls-rprx-vision",
                    "limitIp":    3,
                    "totalGB":    0,
                }]})
            },
            timeout=10
        )
        return resp.json().get("success", False)

    def get_client_traffic(self, email: str) -> dict:
        """
        Статистика трафика клиента по email.
        URL: GET /panel/inbound/getClientTraffics/{email}
        Возвращает: {"up_gb": 0.5, "down_gb": 2.3, "total_gb": 2.8}
        """
        session = self._get_session()
        resp = session.get(
            f"{PANEL_URL}{PANEL_PATH}panel/api/inbounds/getClientTraffics/{email}",
            timeout=10
        )
        data = resp.json()
        if data.get("success") and data.get("obj"):
            obj = data["obj"]
            return {
                "up_gb":    round(obj.get("up", 0) / 1024**3, 2),
                "down_gb":  round(obj.get("down", 0) / 1024**3, 2),
                "total_gb": round(
                    (obj.get("up", 0) + obj.get("down", 0)) / 1024**3, 2
                ),
            }
        return {"up_gb": 0, "down_gb": 0, "total_gb": 0}

    # ── Генерация VLESS ключей ─────────────────────────────────────

    def _build_de_key(self, client_uuid: str) -> str:
        """
        Формирует VLESS ключ для DE сервера.

        Структура:
            vless://{uuid}@{ip}:{port}?{params}#{name}

        Параметры Reality:
            type=tcp              транспорт
            security=reality      тип шифрования
            pbk=                  публичный ключ сервера (из 3x-ui → stream_settings)
            fp=chrome             fingerprint браузера
            sni=yahoo.com         маскировочный домен
            sid=                  short ID (из 3x-ui → stream_settings)
            spx=%2F               spider path
            flow=xtls-rprx-vision режим XTLS
        """
        params = (
            f"type=tcp"
            f"&security=reality"
            f"&pbk={DE_PUBLIC_KEY}"
            f"&fp=chrome"
            f"&sni={DE_SNI}"
            f"&sid={DE_SHORT_ID}"
            f"&spx=%2F"
            f"&flow=xtls-rprx-vision"
        )
        return f"vless://{client_uuid}@{DE_IP}:{DE_PORT}?{params}#🇩🇪 Германия"

    def _build_ru_key(self) -> str:
        """
        Формирует VLESS ключ для RU сервера.

        UUID фиксированный для всех пользователей — это нормально,
        потому что разграничение происходит на уровне файла подписки.
        Каждый пользователь имеет свой уникальный файл /var/www/sub/{sub_id}.
        Если sub_id не известен злоумышленнику — он не получит ключ.
        """
        params = (
            f"type=tcp"
            f"&security=reality"
            f"&pbk={RU_PUBLIC_KEY}"
            f"&fp=chrome"
            f"&sni={RU_SNI}"
            f"&sid={RU_SHORT_ID}"
            f"&spx=%2F"
            f"&flow=xtls-rprx-vision"
        )
        return f"vless://{RU_UUID}@{RU_IP}:{RU_PORT}?{params}#🇷🇺 Россия"

    def _build_subscription_content(self, client_uuid: str) -> bytes:
        """
        Формирует содержимое файла подписки.

        Формат который понимают happ и v2rayTun:
            base64(ключ1\nключ2\n...)

        Приложение декодирует base64 и парсит каждую строку как отдельный ключ.
        Каждый ключ отображается как отдельный профиль в списке серверов.
        """
        de_key  = self._build_de_key(client_uuid)
        ru_key  = self._build_ru_key()
        content = f"{de_key}\n{ru_key}\n"
        return base64.b64encode(content.encode("utf-8"))

    def _write_sub_file(self, sub_id: str, content: bytes) -> None:
        """
        Записывает файл подписки на DE сервер через SFTP.
        Файл: /var/www/sub/{sub_id}
        URL:  https://vpn.test-vpn-spl00.ru:8096/sub/{sub_id}
        """
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=DE_SSH_HOST,
            port=DE_SSH_PORT,
            username=DE_SSH_USER,
            key_filename=DE_SSH_KEY,
            timeout=10        )
        sftp = ssh.open_sftp()
        with sftp.open(f"{SUB_DIR}/{sub_id}", "wb") as f:
            f.write(content)
        sftp.close()
        ssh.close()

    def _delete_sub_file(self, sub_id: str) -> None:
        """Удаляет файл подписки с DE сервера."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=DE_SSH_HOST,
            port=DE_SSH_PORT,
            username=DE_SSH_USER,
            key_filename=DE_SSH_KEY,
            timeout=10
        )
        try:
            sftp = ssh.open_sftp()
            sftp.remove(f"{SUB_DIR}/{sub_id}")
            sftp.close()
        except FileNotFoundError:
            pass
        finally:
            ssh.close()

    def create_subscription(self, user_id: int,
                             subscription_id: int,
                             days: int) -> dict:
        """
        Создаёт полноценную подписку с ключами DE + RU.

        Шаги:
            1. Создаёт клиента в 3x-ui → получает UUID и sub_id
            2. Формирует VLESS ключи для DE и RU
            3. Кодирует в base64
            4. Записывает файл на DE сервер через SSH
            5. Возвращает данные для сохранения в БД

        Параметры:
            telegram_id:     Telegram ID пользователя
            subscription_id: ID записи в таблице subscriptions
            days:            срок действия в днях

        Возвращает:
            {
                "panel_uuid": "нужен для удаления клиента из 3x-ui",
                "sub_id":     "имя файла подписки",
                "sub_link":   "https://vpn.../sub/abc123"
            }
        """
        email  = f"u{user_id}_{subscription_id}"
        client = self.create_panel_client(email, days)

        content = self._build_subscription_content(client["uuid"])
        self._write_sub_file(client["sub_id"], content)

        return {
            "panel_uuid": client["uuid"],
            "sub_id":     client["sub_id"],
            "sub_link":   f"{SUB_BASE_URL}/{client['sub_id']}",
        }

    def delete_subscription(self, panel_uuid: str, sub_id: str) -> None:
        """
        Удаляет подписку полностью:
            1. Удаляет клиента из 3x-ui (ключ перестаёт работать немедленно)
            2. Удаляет файл подписки (ссылка перестаёт работать)
        """
        self.delete_panel_client(panel_uuid)
        self._delete_sub_file(sub_id)

    def renew_subscription(self, telegram_id: int,
                            subscription_id: int,
                            panel_uuid: str,
                            sub_id: str,
                            days: int) -> dict:
        """
        Продлевает подписку:
            1. Обновляет expiryTime в 3x-ui
            2. Файл подписки не меняется — ссылка остаётся прежней

        Возвращает: {"sub_link": "..."}
        """
        email = f"u{telegram_id}_{subscription_id}"
        self.update_panel_client(email, panel_uuid, days)
        return {"sub_link": f"{SUB_BASE_URL}/{sub_id}"}


panel = PanelClient()