# encoding: utf-8


from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError as DjangoValidationError,
)
from mainsite.utils import list_of
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as RestframeworkValidationError


class EntityRelatedFieldV2(serializers.RelatedField):
    def __init__(self, *args, **kwargs):
        self.rel_source = kwargs.pop("rel_source", "entity_id")
        super(EntityRelatedFieldV2, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):
        try:
            obj = self.get_queryset().get(**{self.rel_source: data})
            return obj
        except ObjectDoesNotExist:
            raise RestframeworkValidationError(
                'Invalid {rel_source} "{rel_value}" - object does not exist.'.format(
                    rel_source=self.rel_source, rel_value=data
                )
            )
        except (TypeError, ValueError):
            raise RestframeworkValidationError(
                "Incorrect type. Expected {rel_source} value, got {data_type}.".format(
                    rel_source=self.rel_source, data_type=type(data).__name__
                )
            )

    def to_representation(self, value):
        return getattr(value, self.rel_source)


class BaseSerializerV2(serializers.Serializer):
    _success = True
    _description = "ok"

    @property
    def success(self):
        return self._success

    @success.setter
    def success(self, value):
        self._success = value

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    def __init__(self, *args, **kwargs):
        self.success = kwargs.pop("success", True)
        self.description = kwargs.pop("description", "ok")
        super(BaseSerializerV2, self).__init__(*args, **kwargs)

    @staticmethod
    def response_envelope(
        result, success, description, field_errors=None, validation_errors=None
    ):
        # assert isinstance(result, collections.Sequence)

        envelope = {
            "status": {"success": success, "description": description},
            "result": result,
        }

        if field_errors is not None:
            envelope["fieldErrors"] = field_errors

        if validation_errors is not None:
            envelope["validationErrors"] = validation_errors

        return envelope

    def to_representation(self, instance):
        representation = super(BaseSerializerV2, self).to_representation(instance)
        if self.parent is not None:
            return representation
        else:
            return self.response_envelope(
                result=[representation],
                success=self.success,
                description=self.description,
            )


class ListSerializerV2(serializers.ListSerializer, BaseSerializerV2):
    def to_representation(self, instance):
        representation = super(ListSerializerV2, self).to_representation(instance)
        if self.parent is not None:
            return representation
        else:
            return BaseSerializerV2.response_envelope(
                result=representation,
                success=self.success,
                description=self.description,
            )

    @property
    def data(self):
        return super(serializers.ListSerializer, self).data

    @property
    def errors(self):
        if not hasattr(self, "_errors"):
            msg = "You must call `.is_valid()` before accessing `.errors`."
            raise AssertionError(msg)
        base_errors_list = self._errors

        return_errors = {}
        try:
            for field_errors in base_errors_list:
                for fe_key, fe_value in list(field_errors.items()):
                    if return_errors.get(fe_key) is None:
                        return_errors[fe_key] = field_errors[fe_key]
                    else:
                        return_errors[fe_key] += field_errors[fe_key]

            return return_errors
        except TypeError:
            return base_errors_list


class DetailSerializerV2(BaseSerializerV2):
    entityType = serializers.CharField(
        source="get_entity_class_name", max_length=254, read_only=True
    )
    entityId = serializers.CharField(source="entity_id", max_length=254, read_only=True)

    class Meta:
        list_serializer_class = ListSerializerV2

    def get_model_class(self):
        return getattr(self.Meta, "model", None)

    def create(self, validated_data):
        model_cls = self.get_model_class()
        if model_cls is not None:
            try:
                new_instance = model_cls.objects.create(**validated_data)
            except DjangoValidationError as e:
                raise RestframeworkValidationError(e.message)

            return new_instance

    def update(self, instance, validated_data):
        for field_name, value in list(validated_data.items()):
            setattr(instance, field_name, value)

        save_kwargs = self.context.get("save_kwargs", dict())
        instance.save(**save_kwargs)
        return instance


class V2ErrorSerializer(BaseSerializerV2):
    _field_errors = {}
    _validation_errors = []

    @property
    def field_errors(self):
        return self._field_errors

    @field_errors.setter
    def field_errors(self, value):
        self._field_errors = value

    @property
    def validation_errors(self):
        return self._validation_errors

    @validation_errors.setter
    def validation_errors(self, value):
        self._validation_errors = value

    def __init__(self, *args, **kwargs):
        self.field_errors = kwargs.pop("field_errors", False)
        self.validation_errors = kwargs.pop("validation_errors", ["error"])
        super(V2ErrorSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        try:
            self.validation_errors = self.validation_errors + self.field_errors.pop(
                "non_field_errors", []
            )
        except (TypeError, AttributeError):
            # In the case where field_errors is a list of dicts, we keep non_field_errors grouped with other field
            # errors for that object
            pass

        return BaseSerializerV2.response_envelope(
            result=[],
            success=self.success,
            description=self.description,
            field_errors=self.field_errors,
            validation_errors=self.validation_errors,
        )


class Rfc7591ErrorSerializer(V2ErrorSerializer):
    def to_representation(self, instance):
        errors_list = self.validation_errors
        for key in self.field_errors.keys():
            this_field_errors = self.field_errors.get(key)
            errors_list.append(
                "{}: {}".format(key, str(list_of(this_field_errors[0])[0]))
            )
        return {"error": errors_list[0], "error_description": "; ".join(errors_list)}
