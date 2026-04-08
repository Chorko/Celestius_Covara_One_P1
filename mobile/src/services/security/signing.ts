import CryptoJS from "crypto-js";

export function signDeviceContext(
  rawContext: string,
  timestamp: string,
  secret: string,
): string {
  const canonicalMessage = `${timestamp}.${rawContext}`;
  return CryptoJS.HmacSHA256(canonicalMessage, secret)
    .toString(CryptoJS.enc.Hex)
    .toLowerCase();
}
