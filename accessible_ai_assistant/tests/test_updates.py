import io
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from updates import check_latest


class UpdateTests(unittest.TestCase):
    def test_only_verified_download_replaces_installer(self):
        url = "https://github.com/edre1/Nexo/releases/download/v1.2.3/Nexo-Setup-1.2.3.exe"
        data = b"test installer"
        release = {
            "tag_name": "v1.2.3",
            "html_url": "https://github.com/edre1/Nexo/releases/tag/v1.2.3",
            "assets": [{
                "name": "Nexo-Setup-1.2.3.exe", "browser_download_url": url,
                "size": len(data), "digest": "sha256:" + sha256(data).hexdigest(),
            }],
        }
        with tempfile.TemporaryDirectory() as folder, patch("updates.DATA_ROOT", Path(folder)):
            with patch("updates.urlopen", side_effect=[io.BytesIO(json.dumps(release).encode()), io.BytesIO(data)]):
                version, installer = check_latest(download=True)
            self.assertEqual(version, "v1.2.3")
            self.assertEqual(installer.read_bytes(), data)
            with patch("updates.urlopen", side_effect=[io.BytesIO(json.dumps(release).encode()), io.BytesIO(b"a" * len(data))]):
                with self.assertRaisesRegex(ValueError, "no coincide"):
                    check_latest(download=True)
            self.assertEqual(list(installer.parent.iterdir()), [installer])
            self.assertEqual(installer.read_bytes(), data)
