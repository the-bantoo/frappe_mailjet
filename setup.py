from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in frappe_mailjet/__init__.py
from frappe_mailjet import __version__ as version

setup(
	name="frappe_mailjet",
	version=version,
	description="Syncs mailing lists and reports",
	author="Bantoo",
	author_email="devs@thebantoo.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
