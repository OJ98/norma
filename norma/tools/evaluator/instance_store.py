from uuid import UUID, uuid4

from .model import NormInstance

class NormInstanceStore:
    def __init__(self):
        self.instances: dict[UUID, NormInstance] = {}

    def insert(self, pattern_id: UUID, subject: str, object: str | None = None, project_id: str | None = None) -> UUID:
        instance = NormInstance(
            id=uuid4(),
            pattern_id=pattern_id,
            subject=subject,
            object=object,
            project_id=project_id
        )
        self.instances[instance.id] = instance
        return instance.id
    
    def get(self, instance_id: UUID) -> NormInstance | None:
        try:
            return self.instances[instance_id]
        except KeyError:
            raise KeyError(f"NormInstance with id {instance_id} not found in store.") from None

    def get_all(self) -> list[NormInstance]:
        return list(self.instances.values())