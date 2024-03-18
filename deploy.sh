#!/bin/bash
# This script automates the following steps:
# - Tag a version on the main branch
# - Update the corresponding docker-compose.yml on the prod server
# - Restart the corresponding docker container on the prod server

# Exit if a command failed
set -e

packagesUrl="https://github.com/mint-o-badges/badgr-server/pkgs/container/badgr-server"
productionUrl="openbadges.education"
productionUser="ubuntu"
basePath="/home/ubuntu/docker"
deploymentPath="$basePath/badgr-server"

echo "Enter the commit checksum (e.g. 'f2ed4f8') you want to deploy (leave empty for the latest commit from the remote main)"
read checksum
echo "Enter the major part of the version you want to release (the x in vx.y.z)"
read versionMajor
echo "Enter the minor part of the version you want to release (the y in vx.y.z)"
read versionMinor
echo "Enter the patch part of the version you want to release (the z in vx.y.z)"
read versionPatch
echo "Enter a message you want to add to this tag"
read message

version="v$versionMajor.$versionMinor.$versionPatch"

if [ -z "$checksum" ]; then
    echo "Fetching latest commit..."
    git fetch --all
    checksum=$(git log -n 1 --pretty=format:"%H" origin/main)
    echo "Tagging the latest commit ($checksum) with $version..."
else
    echo "Tagging commit $checksum with version $version..."
fi
git tag -a "$version" $checksum -m "$message"

echo "Pushing tags to origin..."
git push origin --tags

echo -n "Waiting for build to finish..."
while ! curl -s "$packagesUrl" | grep "$version" > /dev/null; do
    echo -n "."
    sleep 1
done
echo ""
echo "Build completed!"

echo "Updating version on production server..."
ssh $productionUser@$productionUrl "sed -i \"s/IMAGE_VERSION=.*/IMAGE_VERSION=\\\"$version\\\"/g\" $deploymentPath/.env"

echo "Committing changes on production server..."
ssh $productionUser@$productionUrl "cd $deploymentPath && git add .env && git commit -m \"Update deployed version of server to $version\""

echo "Restarting all containers..."
echo "Shutting down badgr-ui..."
ssh $productionUser@$productionUrl "cd $basePath/badgr-ui && docker compose down > /dev/null"

echo "Shutting down badgr-server..."
ssh $productionUser@$productionUrl "cd $basePath/badgr-server && docker compose down > /dev/null"

echo "Shutting down https_proxy..."
ssh $productionUser@$productionUrl "cd $basePath/https_proxy && docker compose down > /dev/null"

echo "Starting https_proxy..."
ssh $productionUser@$productionUrl "cd $basePath/https_proxy && docker compose up -d > /dev/null"

echo "Starting badgr-server..."
ssh $productionUser@$productionUrl "cd $basePath/badgr-server && docker compose up -d > /dev/null"

echo "Starting badgr-ui..."
ssh $productionUser@$productionUrl "cd $basePath/badgr-ui && docker compose up -d > /dev/null"

echo "Successfully deployed version $version!"
