#!/usr/bin/env bash
# exit on error
set -o errexit

# Add Microsoft's official GPG key and repository for the driver
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list

# Update the package list and install the ODBC driver
# The ACCEPT_EULA=Y part is to automatically accept the license agreement
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Install our Python libraries from requirements.txt
pip install -r requirements.txt