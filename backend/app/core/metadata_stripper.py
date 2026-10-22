import io
import hashlib
from typing import Dict, Tuple
from PIL import Image


class MetadataStripper:
    """
    Källskyddsverktyg för journalister och utredare.
    Raderar all EXIF-, GPS-, kamera- och enhetsmetadata från digitala bilder
    och dokument för att skydda källor och visselblåsare.
    """

    @staticmethod
    def strip_image_metadata(input_bytes: bytes, format_hint: str = "JPEG") -> Tuple[bytes, Dict[str, str]]:
        """
        Läser in bildens rådata, tar bort all metadata och returnerar rena binärdata.
        Returnerar: (sanitized_bytes, hashes_dict)
        """
        orig_sha256 = hashlib.sha256(input_bytes).hexdigest()

        img = Image.open(io.BytesIO(input_bytes))

        # Skapa en helt ny bild med samma pixeldata men utan EXIF-ordbok
        data = list(img.get_flattened_data())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)

        out_buf = io.BytesIO()
        # Spara utan extra info/exif
        save_format = img.format or format_hint
        if save_format.upper() in ["JPEG", "JPG"]:
            clean_img.save(out_buf, format="JPEG", quality=95)
        elif save_format.upper() == "PNG":
            clean_img.save(out_buf, format="PNG", optimize=True)
        else:
            clean_img.save(out_buf, format=save_format)

        clean_bytes = out_buf.getvalue()
        clean_sha256 = hashlib.sha256(clean_bytes).hexdigest()

        return clean_bytes, {
            "original_sha256": orig_sha256,
            "sanitized_sha256": clean_sha256,
            "status": "METADATA_STRIPPED",
            "format": str(save_format),
        }


metadata_stripper = MetadataStripper()
