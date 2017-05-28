from setuptools import setup, find_packages

setup(
    name='Eridanus',
    version='0.0.0',
    description='Crummy IRC bot',
    url='https://github.com/mithrandi/eridanus',
    install_requires=[
        'Twisted[tls] >= 15.0.0',
        'Mantissa',
        'treq',
        'pyenchant',
        'html5lib',
        'chardet',
        ],
    license='MIT',
    packages=find_packages() + ['axiom.plugins'],
    include_package_data=True)
