"""Cliente Bedrock (Converse API) con límites de frecuencia, presupuesto y manejo de errores.
Credenciales: cadena estándar de boto3 (nunca en código). Solo se crea el cliente con la región."""
from __future__ import annotations

import os
import threading
import time
from collections import deque

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_MODEL = "us.amazon.nova-pro-v1:0"  # valor por defecto del hosting; se sobreescribe con BEDROCK_MODEL_ID


class AIUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class BedrockClient:
    def __init__(self):
        self.model_id = os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL)
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.max_calls = int(os.environ.get("AI_MAX_CALLS", "300"))
        self.per_minute = int(os.environ.get("AI_CALLS_PER_MINUTE", "30"))
        self.max_tokens = int(os.environ.get("AI_MAX_OUTPUT_TOKENS", "1500"))
        self.calls = 0
        self.last_error: str | None = None
        self._recent: deque[float] = deque()
        self._lock = threading.Lock()
        self._sem = threading.Semaphore(int(os.environ.get("AI_CONCURRENCY", "2")))
        self._client = None

    def _cli(self):
        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self.region,
                                        config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 2}))
        return self._client

    def status(self) -> dict:
        return {"model_id": self.model_id, "region": self.region, "calls_used": self.calls, "call_budget": self.max_calls,
                "last_error": self.last_error}

    def converse(self, system: str, messages: list, tools: list | None = None, max_tokens: int | None = None) -> dict:
        with self._lock:
            now = time.time()
            while self._recent and now - self._recent[0] > 60:
                self._recent.popleft()
            if self.calls >= self.max_calls:
                raise AIUnavailable("budget", "Se alcanzó el presupuesto de llamadas a IA configurado.")
            if len(self._recent) >= self.per_minute:
                raise AIUnavailable("rate_limit", "Demasiadas solicitudes por minuto; espera unos segundos.")
            self.calls += 1
            self._recent.append(now)
        kw = dict(modelId=self.model_id, system=[{"text": system}], messages=messages,
                  inferenceConfig={"maxTokens": max_tokens or self.max_tokens, "temperature": 0.2, "topP": 0.9})
        if tools:
            kw["toolConfig"] = {"tools": tools}
        with self._sem:
            try:
                r = self._cli().converse(**kw)
                self.last_error = None
                return r
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "ClientError")
                msg = {"AccessDeniedException": "Sin permiso para usar el modelo en Bedrock.",
                       "ExpiredTokenException": "Las credenciales AWS expiraron; actualiza .env y reinicia el backend.",
                       "UnrecognizedClientException": "Credenciales AWS no válidas.",
                       "ThrottlingException": "Bedrock limitó la solicitud (cuota); reintenta en un momento.",
                       "ValidationException": "Solicitud rechazada por el modelo.",
                       "ResourceNotFoundException": "Modelo no disponible en esta región."}.get(code, f"Error de AWS ({code}).")
                self.last_error = msg
                raise AIUnavailable(code, msg)
            except BotoCoreError as e:
                self.last_error = "No se pudo contactar a Bedrock (red/credenciales)."
                raise AIUnavailable("network", self.last_error) from e


bedrock = BedrockClient()
