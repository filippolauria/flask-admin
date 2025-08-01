import os
import os.path as op
import typing as t
from urllib.parse import urljoin

from markupsafe import Markup
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from wtforms import __version__ as wtforms_version
from wtforms import Field
from wtforms import fields
from wtforms import ValidationError
from wtforms.form import BaseForm
from wtforms.utils import unset_value
from wtforms.utils import UnsetValue
from wtforms.widgets import html_params

from flask_admin._compat import string_types
from flask_admin._types import T_PIL_IMAGE
from flask_admin._types import T_VALIDATOR
from flask_admin.babel import gettext
from flask_admin.helpers import get_theme
from flask_admin.helpers import get_url

try:
    from PIL import Image
    from PIL import ImageOps
except ImportError:
    Image = None  # type:ignore[assignment]
    ImageOps = None  # type:ignore[assignment]

__all__ = [
    "FileUploadInput",
    "FileUploadField",
    "ImageUploadInput",
    "ImageUploadField",
    "namegen_filename",
    "thumbgen_filename",
]


# Widgets
class FileUploadInput:
    """
    Renders a file input chooser field.

    You can customize `empty_template` and `data_template` members to customize
    look and feel.
    """

    # This dictionary holds the default templates for each theme.
    _templates = {
        "bootstrap4": {
            "empty_template": ("<input %(file)s>"),
            "data_template": (
                "<div>"
                " <input %(text)s>"
                ' <input type="checkbox" name="%(marker)s">Delete</input>'
                "</div>"
                "<input %(file)s>"
            ),
        },
        "bootstrap5": {
            "empty_template": '<input class="form-control" %(file)s>',
            "data_template": (
                '<div class="d-flex align-items-center gap-1">'
                '  <input class="form-control" %(text)s>'
                "  <input %(file)s>"
                '  <span class="d-inline-block" tabindex="0" data-bs-toggle="popover"'
                '    data-bs-placement="top" data-bs-trigger="hover"'
                '    data-bs-content="Delete on submit?">'
                '    <div class="bg-body-secondary py-1 px-2 rounded">'
                '      <div class="form-check form-switch">'
                '        <label for="%(marker)s" class="form-check-label text-danger">'
                '          <i class="fas fa-trash"></i>'
                "        </label>"
                '        <input class="form-check-input" role="switch" type="checkbox"'
                '          name="%(marker)s" id="%(marker)s">'
                "      </div>"
                "    </div>"
                "  </span>"
                "</div>"
            ),
        },
    }

    input_type = "file"

    def __call__(self, field: Field, **kwargs: str) -> Markup:
        kwargs.setdefault("id", field.id)
        kwargs.setdefault("name", field.name)

        # 1. Get the active theme and its default configuration.
        _theme = get_theme()
        templates = self._templates.get(_theme, self._templates["bootstrap4"])

        if not hasattr(self, "data_template") and not hasattr(self, "empty_template"):
            # If neither template is defined, use the default from the config.
            empty_template = templates["empty_template"]
            data_template = templates["data_template"]

            # set the templates as attributes of the class instance
            kwargs.setdefault("class", "form-control")

        template = data_template if field.data else empty_template

        if field.errors:
            template = empty_template

        value = (
            field.data.filename
            if isinstance(field.data, FileStorage)
            else (field.data or "")
        )

        return Markup(
            template
            % {
                "text": html_params(
                    type="text", readonly="readonly", value=value, name=field.name
                ),
                "file": html_params(type=self.input_type, value=value, **kwargs),
                "marker": f"_{field.name}-delete",
            }
        )


class ImageUploadInput:
    """
    Renders a image input chooser field.

    You can customize `empty_template` and `data_template` members to customize
    look and feel.
    """

    # This dictionary holds the default templates for each theme.
    _templates = {
        "bootstrap4": {
            "empty_template": ("<input %(file)s>"),
            "data_template": (
                '<div class="image-thumbnail">'
                " <img %(image)s>"
                ' <input type="checkbox" name="%(marker)s">Delete</input>'
                " <input %(text)s>"
                "</div>"
                "<input %(file)s>"
            ),
        },
        "bootstrap5": {
            "empty_template": '<input class="form-control" %(file)s>',
            "data_template": (
                '<div class="image-thumbnail d-flex align-items-center gap-1">'
                '  <img class="img-thumbnail" %(image)s>'
                "  <input %(file)s>"
                '  <span class="d-inline-block" tabindex="0" data-bs-toggle="popover"'
                '    data-bs-placement="top" data-bs-trigger="hover"'
                '    data-bs-content="Delete on submit?">'
                '    <div class="bg-body-secondary py-1 px-2 rounded">'
                '      <div class="form-check form-switch">'
                '        <label for="%(marker)s" class="form-check-label text-danger">'
                '          <i class="fas fa-trash"></i>'
                "        </label>"
                '        <input class="form-check-input" role="switch" type="checkbox"'
                '          name="%(marker)s" id="%(marker)s">'
                "      </div>"
                "    </div>"
                "  </span>"
                "</div>"
            ),
        },
    }

    input_type = "file"

    def __call__(self, field: "ImageUploadField", **kwargs: str) -> Markup:
        kwargs.setdefault("id", field.id)
        kwargs.setdefault("name", field.name)

        # 1. Get the active theme and its default configuration.
        _theme = get_theme()
        templates = self._templates.get(_theme, self._templates["bootstrap4"])

        if not hasattr(self, "data_template") and not hasattr(self, "empty_template"):
            # If neither template is defined, use the default from the config.
            empty_template = templates["empty_template"]
            data_template = templates["data_template"]

            # set the templates as attributes of the class instance
            kwargs.setdefault("class", "form-control")

        args = {
            "text": html_params(type="hidden", value=field.data, name=field.name),
            "file": html_params(type=self.input_type, **kwargs),
            "marker": f"_{field.name}-delete",
        }

        if field.data and isinstance(field.data, string_types):
            url = self.get_url(field)
            args["image"] = html_params(src=url)

            template = data_template
        else:
            template = empty_template

        return Markup(template % args)

    def get_url(self, field: "ImageUploadField") -> str:
        if field.thumbnail_size:
            filename = field.thumbnail_fn(field.data)  # type:ignore[arg-type]
        else:
            filename = field.data  # type:ignore[assignment]

        if field.url_relative_path:
            filename = urljoin(field.url_relative_path, filename)

        return get_url(field.endpoint, filename=filename)  # type:ignore[arg-type]


# Fields
class FileUploadField(fields.StringField):
    """
    Customizable file-upload field.

    Saves file to configured path, handles updates and deletions. Inherits from
    `StringField`, resulting filename will be stored as string.
    """

    widget = FileUploadInput()

    def __init__(
        self,
        label: t.Optional[str] = None,
        validators: t.Optional[list[T_VALIDATOR]] = None,
        base_path: t.Optional[str] = None,
        relative_path: t.Optional[str] = None,
        namegen: t.Optional[t.Callable[[t.Any, FileStorage], str]] = None,
        allowed_extensions: t.Optional[t.Sequence[str]] = None,
        permission: int = 0o666,
        allow_overwrite: bool = True,
        **kwargs: t.Any,
    ) -> None:
        """
        Constructor.

        :param label:
            Display label
        :param validators:
            Validators
        :param base_path:
            Absolute path to the directory which will store files
        :param relative_path:
            Relative path from the directory. Will be prepended to the file name for
            uploaded files. Flask-Admin uses `urlparse.urljoin` to generate resulting
            filename, so make sure you have trailing slash.
        :param namegen:
            Function that will generate filename from the model and uploaded file
            object. Please note, that model is "dirty" model object, before it was
            committed to database.

            For example::

                import os.path as op

                def prefix_name(obj, file_data):
                    parts = op.splitext(file_data.filename)
                    return secure_filename('file-%s%s' % parts)

                class MyForm(BaseForm):
                    upload = FileUploadField('File', namegen=prefix_name)

        :param allowed_extensions:
            List of allowed extensions. If not provided, will allow any file.
        :param allow_overwrite:
            Whether to overwrite existing files in upload directory. Defaults to `True`.

        .. versionadded:: 1.1.1
            The `allow_overwrite` parameter was added.
        """
        self.base_path = base_path
        self.relative_path = relative_path

        self.namegen = namegen or namegen_filename
        self.allowed_extensions = allowed_extensions
        self.permission = permission
        self._allow_overwrite = allow_overwrite

        self._should_delete = False

        if int(wtforms_version[0]) < 3:
            kwargs.pop("extra_filters", None)

        super().__init__(
            label,
            validators,
            **kwargs,
        )

    def is_file_allowed(self, filename: str) -> bool:
        """
        Check if file extension is allowed.

        :param filename:
            File name to check
        """
        if not self.allowed_extensions:
            return True

        return "." in filename and filename.rsplit(".", 1)[1].lower() in map(
            lambda x: x.lower(), self.allowed_extensions
        )

    def _is_uploaded_file(
        self, data: t.Union[FileStorage, None, str]
    ) -> t.Union[FileStorage, None, bool, str]:
        return data and isinstance(data, FileStorage) and data.filename

    def pre_validate(self, form: BaseForm) -> None:
        if self._is_uploaded_file(self.data) and not self.is_file_allowed(
            self.data.filename  # type:ignore[union-attr]
        ):
            raise ValidationError(gettext("Invalid file extension"))

        # Handle overwriting existing content
        if not self._is_uploaded_file(self.data):
            return

        if not self._allow_overwrite and os.path.exists(
            self._get_path(
                self.data.filename  # type:ignore[union-attr]
            )
        ):
            raise ValidationError(
                gettext(
                    f'File "{self.data.filename}" already exists.'  # type:ignore[union-attr]
                )
            )

    def process(
        self,
        formdata: dict,  # type:ignore[override]
        data: UnsetValue = unset_value,
        extra_filters: t.Optional[t.Sequence] = None,
    ) -> None:
        if formdata:
            marker = f"_{self.name}-delete"
            if marker in formdata:
                self._should_delete = True

        if int(wtforms_version[0]) < 3:
            return super().process(formdata, data)  # type:ignore[arg-type]
        else:
            return super(FileUploadField, self).process(  # noqa
                formdata,  # type: ignore[arg-type]
                data,
                extra_filters,
            )

    def process_formdata(self, valuelist: list[t.Union[str, FileStorage]]) -> None:
        if self._should_delete:
            self.data = None
        elif valuelist:
            for data in valuelist:
                if self._is_uploaded_file(data):
                    self.data = data  # type:ignore[assignment]
                    break

    def populate_obj(self, obj: t.Any, name: str) -> None:
        field = getattr(obj, name, None)
        if field:
            # If field should be deleted, clean it up
            if self._should_delete:
                self._delete_file(field)
                setattr(obj, name, None)
                return

        if self._is_uploaded_file(self.data):
            if field:
                self._delete_file(field)

            filename = self.generate_name(obj, self.data)  # type:ignore[arg-type]
            filename = self._save_file(self.data, filename)  # type:ignore[arg-type]
            # update filename of FileStorage to our validated name
            self.data.filename = filename  # type: ignore[union-attr]

            setattr(obj, name, filename)

    def generate_name(self, obj: t.Any, file_data: FileStorage) -> str:
        filename = self.namegen(obj, file_data)

        if not self.relative_path:
            return filename

        return urljoin(self.relative_path, filename)

    def _get_path(self, filename: str) -> str:
        if not self.base_path:
            raise ValueError("FileUploadField field requires base_path to be set.")

        if callable(self.base_path):
            return op.join(self.base_path(), filename)
        return op.join(self.base_path, filename)

    def _delete_file(self, filename: str) -> None:
        path = self._get_path(filename)

        if op.exists(path):
            os.remove(path)

    def _save_file(self, data: FileStorage, filename: str) -> str:
        path = self._get_path(filename)
        if not op.exists(op.dirname(path)):
            os.makedirs(os.path.dirname(path), self.permission | 0o111)

        if (self._allow_overwrite is False) and os.path.exists(path):
            raise ValueError(gettext(f'File "{path}" already exists.'))

        data.save(path)

        return filename


class ImageUploadField(FileUploadField):
    """
    Image upload field.

    Does image validation, thumbnail generation, updating and deleting images.

    Requires PIL (or Pillow) to be installed.
    """

    widget = ImageUploadInput()  # type: ignore[assignment]

    keep_image_formats = ("PNG",)
    """
        If field detects that uploaded image is not in this list, it will save image
        as PNG.
    """

    def __init__(
        self,
        label: t.Optional[str] = None,
        validators: t.Optional[list[T_VALIDATOR]] = None,
        base_path: t.Optional[str] = None,
        relative_path: t.Optional[str] = None,
        namegen: t.Optional[t.Callable[[t.Any, FileStorage], str]] = None,
        allowed_extensions: t.Optional[t.Sequence[str]] = None,
        max_size: t.Optional[tuple[int, int, bool]] = None,
        thumbgen: t.Optional[t.Callable[[str], str]] = None,
        thumbnail_size: t.Optional[tuple[int, int, bool]] = None,
        permission: int = 0o666,
        url_relative_path: t.Optional[str] = None,
        endpoint: t.Optional[str] = "static",
        **kwargs: t.Any,
    ) -> None:
        """
        Constructor.

        :param label:
            Display label
        :param validators:
            Validators
        :param base_path:
            Absolute path to the directory which will store files
        :param relative_path:
            Relative path from the directory. Will be prepended to the file name for
            uploaded files. Flask-Admin uses `urlparse.urljoin` to generate resulting
            filename, so make sure you have trailing slash.
        :param namegen:
            Function that will generate filename from the model and uploaded file
            object. Please note, that model is "dirty" model object, before it was
            committed to database.

            For example::

                import os.path as op

                def prefix_name(obj, file_data):
                    parts = op.splitext(file_data.filename)
                    return secure_filename('file-%s%s' % parts)

                class MyForm(BaseForm):
                    upload = FileUploadField('File', namegen=prefix_name)

        :param allowed_extensions:
            List of allowed extensions. If not provided, then gif, jpg, jpeg, png and
            tiff will be allowed.
        :param max_size:
            Tuple of (width, height, force) or None. If provided, Flask-Admin will
            resize image to the desired size.

            Width and height is in pixels. If `force` is set to `True`, will try to fit
            image into dimensions and keep aspect ratio, otherwise will just resize to
            target size.
        :param thumbgen:
            Thumbnail filename generation function. All thumbnails will be saved as
            JPEG files, so there's no need to keep original file extension.

            For example::

                import os.path as op

                def thumb_name(filename):
                    name, _ = op.splitext(filename)
                    return secure_filename('%s-thumb.jpg' % name)

                class MyForm(BaseForm):
                    upload = ImageUploadField('File', thumbgen=thumb_name)

        :param thumbnail_size:
            Tuple or (width, height, force) values. If not provided, thumbnail won't be
            created.

            Width and height is in pixels. If `force` is set to `True`, will try to fit
            image into dimensions and keep aspect ratio, otherwise will just resize to
            target size.
        :param url_relative_path:
            Relative path from the root of the static directory URL. Only gets used
            when generating preview image URLs.

            For example, your model might store just file names (`relative_path` set
            to `None`), but `base_path` is pointing to subdirectory.
        :param endpoint:
            Static endpoint for images. Used by widget to display previews. Defaults
            to 'static'.
        """
        # Check if PIL is installed
        if Image is None:
            raise Exception(
                "Could not import `PIL`. "
                "Enable `images` integration by installing `flask-admin[images]`"
            )

        self.max_size = max_size
        self.thumbnail_fn = thumbgen or thumbgen_filename
        self.thumbnail_size = thumbnail_size
        self.endpoint = endpoint
        self.image: t.Optional[T_PIL_IMAGE] = None
        self.url_relative_path = url_relative_path

        if not allowed_extensions:
            allowed_extensions = ("gif", "jpg", "jpeg", "png", "tiff")

        super().__init__(
            label,
            validators,
            base_path=base_path,
            relative_path=relative_path,
            namegen=namegen,
            allowed_extensions=allowed_extensions,
            permission=permission,
            **kwargs,
        )

    def pre_validate(self, form: BaseForm) -> None:
        super().pre_validate(form)

        if self._is_uploaded_file(self.data):
            try:
                self.image = Image.open(self.data)  # type:ignore[arg-type]
            except Exception as e:
                raise ValidationError(f"Invalid image: {e}") from e

    # Deletion
    def _delete_file(self, filename: str) -> None:
        super()._delete_file(filename)

        self._delete_thumbnail(filename)

    def _delete_thumbnail(self, filename: str) -> None:
        path = self._get_path(self.thumbnail_fn(filename))

        if op.exists(path):
            os.remove(path)

    # Saving
    def _save_file(self, data: FileStorage, filename: str) -> str:
        path = self._get_path(filename)

        if not op.exists(op.dirname(path)):
            os.makedirs(os.path.dirname(path), self.permission | 0o111)

        # Figure out format
        filename, format = self._get_save_format(
            filename,
            self.image,  # type:ignore[arg-type]
        )

        if self.image and (self.image.format != format or self.max_size):
            if self.max_size:
                image = self._resize(self.image, self.max_size)
            else:
                image = self.image

            self._save_image(image, self._get_path(filename), format)
        else:
            data.seek(0)
            data.save(self._get_path(filename))

        self._save_thumbnail(data, filename, format)

        return filename

    def _save_thumbnail(self, data: FileStorage, filename: str, format: str) -> None:
        if self.image and self.thumbnail_size:
            path = self._get_path(self.thumbnail_fn(filename))

            self._save_image(
                self._resize(self.image, self.thumbnail_size), path, format
            )

    def _resize(self, image: T_PIL_IMAGE, size: tuple[int, int, bool]) -> T_PIL_IMAGE:
        (width, height, force) = size

        if image.size[0] > width or image.size[1] > height:
            if force:
                return ImageOps.fit(
                    self.image,  # type: ignore[arg-type]
                    (width, height),
                    Image.Resampling.LANCZOS,
                )
            else:
                thumb = self.image.copy()  # type: ignore[union-attr]
                thumb.thumbnail((width, height), Image.Resampling.LANCZOS)
                return thumb

        return image

    def _save_image(self, image: T_PIL_IMAGE, path: str, format: str = "JPEG") -> None:
        # New Pillow versions require RGB format for JPEGs
        if format == "JPEG" and image.mode != "RGB":
            image = image.convert("RGB")
        elif image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        with open(path, "wb") as fp:
            image.save(fp, format)

    def _get_save_format(self, filename: str, image: T_PIL_IMAGE) -> tuple[str, str]:
        if image.format not in self.keep_image_formats:
            name, ext = op.splitext(filename)
            filename = f"{name}.jpg"
            return filename, "JPEG"

        return filename, image.format


# Helpers
def namegen_filename(obj: t.Any, file_data: FileStorage) -> str:
    """
    Generate secure filename for uploaded file.
    """
    return secure_filename(file_data.filename)  # type:ignore[arg-type]


def thumbgen_filename(filename: str) -> str:
    """
    Generate thumbnail name from filename.
    """
    name, ext = op.splitext(filename)
    return f"{name}_thumb{ext}"
