import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Alertrace API"
    app_version: str = "1.1.0"
    environment: str = "production"
    
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    
    supabase_url: str
    supabase_key: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # ========== ALCHEMY ACCOUNT KIT CONFIGURATION ==========
    alchemy_jwt_kid: str
    alchemy_audience_id: str
    api_domain: str
    alchemy_private_key_path: str = "./keys/alchemy_private_key.pem"
    alchemy_public_key_path: str = "./keys/alchemy_public_key.pem"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    def get_alchemy_private_key(self) -> str:
        """Lee la clave privada RSA para Alchemy JWT"""
        # Las claves están en backend/keys/, path es relativo a raíz del proyecto
        key_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # Sube 3 niveles a raíz
            self.alchemy_private_key_path
        )
        with open(key_path, 'r') as f:
            return f.read()

    def get_alchemy_public_key(self) -> str:
        """Lee la clave pública RSA para Alchemy JWT"""
        # Las claves están en backend/keys/, path es relativo a raíz del proyecto
        key_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # Sube 3 niveles a raíz
            self.alchemy_public_key_path
        )
        with open(key_path, 'r') as f:
            return f.read()

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore" # Ignora variables extra en el .env

settings = Settings()