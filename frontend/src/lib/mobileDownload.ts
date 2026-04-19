export interface MobileDownloadLinks {
  androidUrl: string;
  iosUrl: string;
  webUrl: string;
  fallbackUrl: string;
}

function cleaned(value: string | undefined): string {
  if (!value) {
    return "";
  }
  return value.trim();
}

export function getMobileDownloadLinks(): MobileDownloadLinks {
  return {
    androidUrl: cleaned(process.env.NEXT_PUBLIC_MOBILE_DOWNLOAD_ANDROID_URL),
    iosUrl: cleaned(process.env.NEXT_PUBLIC_MOBILE_DOWNLOAD_IOS_URL),
    webUrl: cleaned(process.env.NEXT_PUBLIC_MOBILE_DOWNLOAD_WEB_URL),
    fallbackUrl: cleaned(process.env.NEXT_PUBLIC_MOBILE_DOWNLOAD_FALLBACK_URL),
  };
}

export function resolveDownloadTarget(
  links: MobileDownloadLinks,
  platform?: string | null,
  userAgent?: string | null,
): string {
  const normalizedPlatform = (platform || "").toLowerCase();
  const ua = (userAgent || "").toLowerCase();

  if (normalizedPlatform === "android" && links.androidUrl) {
    return links.androidUrl;
  }

  if ((normalizedPlatform === "ios" || normalizedPlatform === "iphone") && links.iosUrl) {
    return links.iosUrl;
  }

  if ((normalizedPlatform === "web" || normalizedPlatform === "expo") && links.webUrl) {
    return links.webUrl;
  }

  const looksAndroid = ua.includes("android");
  const looksIos = ua.includes("iphone") || ua.includes("ipad") || ua.includes("ipod");

  if (looksAndroid && links.androidUrl) {
    return links.androidUrl;
  }

  if (looksIos && links.iosUrl) {
    return links.iosUrl;
  }

  if (links.fallbackUrl) {
    return links.fallbackUrl;
  }

  if (links.webUrl) {
    return links.webUrl;
  }

  if (links.androidUrl) {
    return links.androidUrl;
  }

  if (links.iosUrl) {
    return links.iosUrl;
  }

  return "";
}
