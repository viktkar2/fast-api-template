import datetime
import logging

from src.domain.models.entities.user import UserDocument

logger = logging.getLogger(__name__)


class UserService:
    async def upsert_user(
        self,
        entra_object_id: str,
        display_name: str,
        email: str,
    ) -> UserDocument:
        """Sync user from JWT claims into the local users collection (insert or update)."""
        user = await UserDocument.find_one(
            UserDocument.entra_object_id == entra_object_id
        )

        if user is None:
            user = UserDocument(
                entra_object_id=entra_object_id,
                display_name=display_name,
                email=email,
            )
            await user.insert()
            logger.info(
                "Created new local user for entra_object_id=%s", entra_object_id
            )
        else:
            user.display_name = display_name
            user.email = email
            user.updated_at = datetime.datetime.now(datetime.UTC)
            await user.save()

        return user
