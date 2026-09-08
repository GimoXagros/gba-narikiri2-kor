"""Verified, non-overwriting publication of a newly created local file."""
import os
from pathlib import Path
import uuid


def exists_or_link(path):
    return path.exists() or path.is_symlink()


def atomic_write_new(path, data):
    """Never expose a partially written destination, including on ENOSPC.

    Windows rename fails when the destination exists (also on FAT volumes).
    POSIX uses an exclusive hard-link publication and fails safely on a
    filesystem without link support. No overwriting rename fallback is used.
    """
    path = Path(path)
    if exists_or_link(path):
        raise FileExistsError('Output exists; choose a new filename')
    parent = path.parent.resolve(strict=True)
    temporary = parent / ('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    published = False
    identity = None
    try:
        with temporary.open('xb') as stream:
            if stream.write(data) != len(data):
                raise OSError('Short output write')
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != data:
            raise OSError('Staged output read-back mismatch')
        stat = temporary.stat()
        identity = (stat.st_dev, stat.st_ino)
        if os.name == 'nt':
            os.rename(temporary, path)
        else:
            os.link(temporary, path)
        published = True
        if path.read_bytes() != data:
            raise OSError('Published output read-back mismatch')
    except BaseException:
        # Only remove a final file we created and still own, never a preexisting
        # file or a concurrently substituted pathname.
        if published and path.exists() and not path.is_symlink():
            stat = path.stat()
            if (stat.st_dev, stat.st_ino) == identity:
                path.unlink()
        raise
    finally:
        if temporary.exists():
            temporary.unlink()
