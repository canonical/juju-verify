from setuptools import setup, find_packages

requirements = [
    'juju'
]

dev_requirements = [
    'pylint',
    'mypy',
    'pytest',
    'coverage'
]

setup(
    name='juju_verify',
    version='0.1',
    description='Juju plugin to verify if it\'s safe to perform action on the '
                'unit',
    packages=find_packages(exclude=['tests']),
    entry_points={'console_scripts': ['juju-verify = juju_verify:main']},
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements
    }
)