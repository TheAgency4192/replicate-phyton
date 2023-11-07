from typing import List, Optional, Union

from typing_extensions import deprecated

from replicate.model import Model
from replicate.pagination import Page
from replicate.resource import Namespace, Resource


class Collection(Resource):
    """
    A collection of models on Replicate.
    """

    slug: str
    """The slug used to identify the collection."""

    name: str
    """The name of the collection."""

    description: str
    """A description of the collection."""

    models: Optional[List[Model]] = None
    """The models in the collection."""

    @property
    @deprecated("Use `slug` instead of `id`")
    def id(self) -> str:
        """
        DEPRECATED: Use `slug` instead.
        """
        return self.slug

    def __iter__(self):  # noqa: ANN204
        return iter(self.models)

    def __getitem__(self, index) -> Optional[Model]:
        if self.models is not None:
            return self.models[index]

        return None

    def __len__(self) -> int:
        if self.models is not None:
            return len(self.models)

        return 0


class Collections(Namespace):
    """
    A namespace for operations related to collections of models.
    """

    def list(self, cursor: Union[str, "ellipsis"] = ...) -> Page[Collection]:  # noqa: F821
        """
        List collections of models.

        Parameters:
            cursor: The cursor to use for pagination. Use the value of `Page.next` or `Page.previous`.
        Returns:
            Page[Collection]: A page of of model collections.
        Raises:
            ValueError: If `cursor` is `None`.
        """

        if cursor is None:
            raise ValueError("cursor cannot be None")

        resp = self._client._request(
            "GET", "/v1/collections" if cursor is ... else cursor
        )

        obj = resp.json()
        obj["results"] = [Collection(**result) for result in obj["results"]]

        return Page[Collection](**obj)

    def get(self, slug: str) -> Collection:
        """Get a model by name.

        Args:
            name: The name of the model, in the format `owner/model-name`.
        Returns:
            The model.
        """

        resp = self._client._request("GET", f"/v1/collections/{slug}")

        return Collection(**resp.json())
