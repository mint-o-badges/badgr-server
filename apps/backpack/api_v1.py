from rest_framework import permissions, status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from backpack.models import BackpackCollectionBadgeInstance, BackpackCollection
from backpack.serializers_v1 import CollectionBadgeSerializerV1
from issuer.models import BadgeInstance

from drf_spectacular.utils import extend_schema_view, extend_schema, inline_serializer


@extend_schema_view(
    get=extend_schema(
        summary="Get badges in a collection",
        description="Retrieve all badges that belong to a specific collection",
        tags=["Collections"],
        responses={
            200: CollectionBadgeSerializerV1(many=True),
            404: {"description": "Collection not found"},
        },
    ),
    post=extend_schema(
        summary="Add badges to collection",
        description="Add one or more badges to an existing collection",
        tags=["Collections"],
        request=CollectionBadgeSerializerV1,
        responses={
            201: CollectionBadgeSerializerV1,
            400: {"description": "No new records could be added"},
            404: {"description": "Collection not found"},
        },
    ),
    put=extend_schema(
        summary="Update collection badges",
        description="Replace the entire list of badges in a collection",
        tags=["Collections"],
        request=CollectionBadgeSerializerV1,
        responses={
            200: CollectionBadgeSerializerV1,
            404: {"description": "Collection not found"},
        },
    ),
)
class CollectionLocalBadgeInstanceList(APIView):
    """
    POST to add badges to collection, PUT to update collection to a new list of
    ids.
    """

    queryset = BackpackCollectionBadgeInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, slug, **kwargs):
        """
        GET the badges in a single Collection
        """
        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id(slug)
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if collection.created_by != request.user:
            return Response(status=status.HTTP_404_NOT_FOUND)

        collection_badges = collection.cached_collects()

        serializer = CollectionBadgeSerializerV1(collection_badges, many=True)
        return Response(serializer.data)

    def post(self, request, slug, **kwargs):
        """
        POST new badge(s) to add them to a existing Collection.
        Returns resulting complete list of collection contents.
        """
        try:
            collection = BackpackCollection.objects.get(
                created_by=request.user, entity_id=slug
            )
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        add_many = isinstance(request.data, list)
        serializer = CollectionBadgeSerializerV1(
            data=request.data,
            many=add_many,
            context={
                "collection": collection,
                "request": request,
                "user": request.user,
                "add_only": True,
            },
        )
        serializer.is_valid(raise_exception=True)

        new_records = serializer.save()

        if new_records == []:
            return Response(
                (
                    "No new records could be added to collection. "
                    + "Check for missing/unknown badge references, unauthorized "
                    + "access, or badges already existing in collection."
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, slug, **kwargs):
        """
        Update the list of badges included in a collection among
        those added to the logged-in user's badges. Cannot be used to
        change the description of a badge in the collection, but can
        be used to add descriptions to new badges to be added from the
        user's existing badges. Cannot be used to add new badges to the
        user's account at this time.
        ---
        parameters:
            - name: slug
              description: The collection's slug identifier
              required: true
              type: string
              paramType: path
            - name: badges
              description: A JSON serialization of all the badges to be
              included in this collection, replacing the list that currently exists.
              required: true
              paramType: body
        """
        badges = request.data

        try:
            collection = BackpackCollection.objects.get(
                created_by=request.user, entity_id=slug
            )
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = CollectionBadgeSerializerV1(
            data=badges, many=True, context={"collection": collection}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(
        summary="Get a specific badge in a collection",
        description="Retrieve details of a single badge within a collection",
        tags=["Collections"],
        responses={
            200: CollectionBadgeSerializerV1,
            404: {"description": "Collection or badge not found"},
        },
    ),
    delete=extend_schema(
        summary="Remove badge from collection",
        description="Remove a badge from a collection (does not delete it from the earner's account)",
        tags=["Collections"],
        responses={
            204: {"description": "Badge removed successfully"},
            404: {"description": "Collection or badge not found"},
        },
    ),
)
class CollectionLocalBadgeInstanceDetail(APIView):
    """
    Update details on a single item in the collection or remove it from the
    collection.
    """

    queryset = BackpackCollectionBadgeInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, **kwargs):
        collection_slug = kwargs.get("collection_slug", None)
        slug = kwargs.get("slug", None)
        if not collection_slug or not slug:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id(
                collection_slug
            )
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if collection.created_by != request.user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        badge_instance = None
        try:
            badge_instance = BadgeInstance.cached.get(entity_id=slug)
        except BadgeInstance.DoesNotExist:
            pass
        try:
            if not badge_instance:
                badge_instance = BadgeInstance.objects.get(slug=slug)
        except BadgeInstance.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        item = None
        for collect in collection.cached_collects():
            if collect.badgeinstance_id == badge_instance.id:
                item = collect
                break
        if item is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = CollectionBadgeSerializerV1(item)
        return Response(serializer.data)

    # def put(self, request, collection_slug, badge_id):
    #     """
    #     Update the description of a badge in a collection.
    #     ---
    #     parameters:
    #         - name: description
    #           description: Earner's annotation about a badge particular to this collection's audience.
    #           required: true
    #           type: string
    #           paramType: form
    #         - name: collection_slug
    #           description: The collection's slug identifier
    #           required: true
    #           type: string
    #           paramType: path
    #         - name: badge_id
    #           description: The stored badge's integer identifier
    #           required: true
    #           type: integer
    #           paramType: path
    #     """
    #     description = request.data.get('description', '')
    #
    #     try:
    #         description = str(description)
    #     except TypeError:
    #         return serializers.ValidationError(
    #             "Server could not understand description")
    #
    #     item = LocalBadgeInstanceCollection.objects.find(request.user, collection_slug, badge_id)
    #     if item is None:
    #         return Response(status=status.HTTP_404_NOT_FOUND)
    #
    #     item.description = description
    #     item.save()
    #
    #     serializer = CollectionBadgeSerializer(item)
    #     return Response(serializer.data)

    def delete(self, request, **kwargs):
        """
        Remove a badge from a collection (does not delete it
        from the earner's account)
        ---
        parameters:
            - name: collection_slug
              description: The collection's slug identifier
              required: true
              type: string
              paramType: path
            - name: badge_id
              description: The stored badge's integer identifier
              required: true
              type: integer
              paramType: path
        """
        collection_slug = kwargs.get("collection_slug")
        slug = kwargs.get("slug")
        if not collection_slug or not slug:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id(
                collection_slug
            )
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if collection.created_by != request.user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        badge_instance = None
        try:
            badge_instance = BadgeInstance.cached.get(entity_id=slug)
        except BadgeInstance.DoesNotExist:
            pass
        try:
            if not badge_instance:
                badge_instance = BadgeInstance.objects.get(slug=slug)
        except BadgeInstance.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        item = None
        for collect in collection.cached_collects():
            if collect.badgeinstance_id == badge_instance.id:
                item = collect
                break
        if item is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        summary="Generate shareable URL for collection",
        description="Make a collection public by generating a shareable hash and return the share URL",
        tags=["Collections"],
        responses={
            200: inline_serializer(
                name="CollectionShareUrlResponse",
                fields={
                    "share_url": serializers.URLField(
                        help_text="The shareable URL for the collection"
                    )
                },
            ),
            404: {"description": "Collection not found"},
        },
    ),
    delete=extend_schema(
        summary="Remove collection share",
        description="Make a collection private by removing its share hash",
        tags=["Collections"],
        responses={
            204: {"description": "Share hash removed successfully"},
            404: {"description": "Collection not found"},
        },
    ),
)
class CollectionGenerateShare(APIView):
    """
    Allows a Collection to be public by generation of a shareable hash.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, slug, **kwargs):
        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id(slug)
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not request.user == collection.owner:
            return Response(status=status.HTTP_404_NOT_FOUND)

        collection.published = True
        collection.save()

        return Response(collection.share_url)

    def delete(self, request, slug, **kwargs):
        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id(slug)
        except BackpackCollection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not request.user == collection.owner:
            return Response(status=status.HTTP_404_NOT_FOUND)

        collection.share_hash = ""
        collection.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
