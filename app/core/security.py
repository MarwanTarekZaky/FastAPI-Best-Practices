from fastapi.security import OAuth2PasswordBearer

oauth2_scheme_seller = OAuth2PasswordBearer(tokenUrl="/seller/token", scheme_name="seller")
oauth2_scheme_partner = OAuth2PasswordBearer(tokenUrl="/partner/token", scheme_name="partner")