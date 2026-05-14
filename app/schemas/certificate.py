"""
app/schemas/certificate.py

Pydantic v2 схемы для эндпоинтов сертификатов.

Карта использования:
  POST  /certificates/{course_id}           →  CertificateResponse
  GET   /certificates/my                    →  list[CertificateResponse]
  GET   /certificates/{certificate_number}  →  CertificateVerifyResponse
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CertificateResponse(BaseModel):
    """
    Ответ API с данными сертификата.

    Возвращается при выдаче и при получении списка сертификатов студента.
    Строится напрямую из ORM-объекта Certificate.
    """

    id: int = Field(description="Уникальный ID записи сертификата")
    user_id: int = Field(description="ID студента, получившего сертификат")
    course_id: int = Field(description="ID курса, за который выдан сертификат")
    issued_at: datetime = Field(description="Дата и время выдачи сертификата (UTC)")
    certificate_number: str = Field(
        description=(
            "Уникальный номер сертификата для верификации. "
            "Формат: CERT-{YEAR}-{8 символов UUID}"
        ),
        examples=["CERT-2024-A1B2C3D4"],
    )

    # from_attributes=True — читаем поля из ORM-объекта Certificate
    model_config = ConfigDict(from_attributes=True)


class CertificateVerifyResponse(BaseModel):
    """
    Расширенный ответ публичного эндпоинта верификации сертификата.

    В отличие от CertificateResponse содержит человекочитаемые поля:
    имя студента и название курса — для отображения на странице верификации
    без дополнительных запросов к API.
    """

    certificate_number: str = Field(
        description="Номер проверяемого сертификата",
        examples=["CERT-2024-A1B2C3D4"],
    )
    issued_at: datetime = Field(description="Дата выдачи сертификата (UTC)")
    course_id: int = Field(description="ID пройденного курса")
    course_title: str = Field(description="Название пройденного курса")
    user_id: int = Field(description="ID студента")
    student_name: str = Field(
        description="Полное имя студента (или email если имя не задано)",
    )
    is_valid: bool = Field(
        default=True,
        description="Всегда True если сертификат найден в БД — подтверждение подлинности",
    )

    model_config = ConfigDict(from_attributes=False)
