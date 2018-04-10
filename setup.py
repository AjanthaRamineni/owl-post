from setuptools import setup, find_packages

setup(name='owlpost',
      packages=find_packages(),
      version='0.1',
      description='To move data to and fro VIVO',
      author='Naomi Braun',
      author_email='naomi.d.braun@gmail.com',
      url='https://github.com/naomidb/owl-post',
      license='Apache License 2.0',
      install_requires=[
          'requests==2.18.4',
          'PyYAML==3.12',
          'Jinja2==2.10'],
      )
