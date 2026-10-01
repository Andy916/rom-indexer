import re
from pathlib import Path


SYSTEMS = {
	".3ds": "Nintendo 3DS",
	".gb": "Nintendo Game Boy",
	".gba": "Nintendo Game Boy Advance",
	".gbc": "Nintendo Game Boy Color",
	".nds": "Nintendo DS",
	".nes": "Nintendo Entertainment System",
	".n64": "Nintendo 64",
	".sfc": "Super Nintendo",
	".smc": "Super Nintendo",
	".iso": "Disc Images",
	".bin": "Disc Images",
	".cue": "Disc Images",
	".chd": "Disc Images",
	".pbp": "PlayStation Portable",
	".psp": "PlayStation Portable",
	".md": "Sega Genesis",
	".gen": "Sega Genesis",
	".sms": "Sega Master System",
	".gg": "Sega Game Gear",
	".gba.gz": "Nintendo Game Boy Advance",
	".nes.gz": "Nintendo Entertainment System",
	".sfc.gz": "Super Nintendo",
	".z64": "Nintendo 64",
	".v64": "Nintendo 64",
	".wud": "Nintendo Wii U",
	".wux": "Nintendo Wii U",
	".rvz": "Nintendo Wii",
	".wbfs": "Nintendo Wii",
}

_NOISE_PATTERNS = (
	re.compile(r"\[[^\]]*\]"),
	re.compile(r"\([^)]*\)"),
	re.compile(r"\b(USA|Europe|Japan|World|En|Fr|De|Es|It|Rev\s*\d+|v\d+(?:\.\d+)*)\b", re.I),
	re.compile(r"\b(Disc|Disk)\s*\d+\b", re.I),
)


def detect_system(filename: str) -> str:
	"""Return a human-readable system name from a ROM filename."""
	lowered = filename.lower()
	for extension in sorted(SYSTEMS, key=len, reverse=True):
		if lowered.endswith(extension):
			return SYSTEMS[extension]
	return "Other"


def clean_title(filename: str) -> str:
	"""Remove the file extension and common release-group noise."""
	title = Path(filename).name
	lowered = title.lower()
	for extension in sorted(SYSTEMS, key=len, reverse=True):
		if lowered.endswith(extension):
			title = title[: -len(extension)]
			break
	else:
		title = Path(title).stem

	for pattern in _NOISE_PATTERNS:
		title = pattern.sub(" ", title)
	title = re.sub(r"\s+-\s+", " ", title)
	title = re.sub(r"[_\.]+", " ", title)
	title = re.sub(r"\s+", " ", title)
	return title.strip(" -_.") or Path(filename).stem
