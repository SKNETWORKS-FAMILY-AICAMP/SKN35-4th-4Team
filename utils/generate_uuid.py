import uuid

def generate_uuid() -> str:
    """VARCHAR(36) PK용 UUID 문자열 생성 (마이그레이션 직렬화를 위해 함수로 분리)"""
    return str(uuid.uuid4())