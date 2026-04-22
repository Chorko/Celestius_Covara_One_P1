const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);
const asyncStorageTransientPattern =
  /node_modules[\/\\]@react-native-async-storage[\/\\]\.async-storage-[^\/\\]+(?:[\/\\].*)?$/;

// Ignore transient temp folders created during package operations on Windows.
if (config.resolver.blockList instanceof RegExp) {
  config.resolver.blockList = new RegExp(
    `${config.resolver.blockList.source}|${asyncStorageTransientPattern.source}`,
  );
} else {
  config.resolver.blockList = asyncStorageTransientPattern;
}

module.exports = config;
