import React from "react";
import { StyleSheet, View } from "react-native";

interface BrandMarkProps {
  size?: number;
}

export function BrandMark({ size = 64 }: BrandMarkProps) {
  const frameSize = size * 0.58;
  const frameOffset = (size - frameSize) / 2;
  const frameStroke = Math.max(2, Math.round(size * 0.05));
  const lineThickness = Math.max(3, Math.round(size * 0.08));

  return (
    <View
      style={[
        styles.shell,
        {
          width: size,
          height: size,
          borderRadius: Math.round(size * 0.28),
        },
      ]}
    >
      <View
        style={[
          styles.halo,
          {
            width: size * 0.82,
            height: size * 0.82,
            borderRadius: size,
          },
        ]}
      />

      <View
        style={[
          styles.frame,
          {
            width: frameSize,
            height: frameSize,
            borderRadius: Math.round(size * 0.18),
            left: frameOffset,
            top: frameOffset,
            borderWidth: frameStroke,
          },
        ]}
      />

      <View
        style={[
          styles.trackA,
          {
            width: size * 0.28,
            height: lineThickness,
            left: size * 0.23,
            top: size * 0.58,
            borderRadius: lineThickness,
          },
        ]}
      />
      <View
        style={[
          styles.trackB,
          {
            width: size * 0.32,
            height: lineThickness,
            left: size * 0.41,
            top: size * 0.53,
            borderRadius: lineThickness,
          },
        ]}
      />

      <View
        style={[
          styles.topSignal,
          {
            width: size * 0.16,
            height: size * 0.16,
            left: size * 0.64,
            top: size * 0.24,
            borderRadius: size,
          },
        ]}
      >
        <View
          style={[
            styles.topSignalInner,
            {
              width: size * 0.07,
              height: size * 0.07,
              borderRadius: size,
            },
          ]}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(185, 255, 227, 0.45)",
    backgroundColor: "#11362B",
    alignItems: "center",
    justifyContent: "center",
  },
  halo: {
    position: "absolute",
    backgroundColor: "rgba(42, 193, 137, 0.22)",
  },
  frame: {
    position: "absolute",
    borderColor: "rgba(194, 255, 233, 0.92)",
  },
  trackA: {
    position: "absolute",
    backgroundColor: "#B7FFE2",
    transform: [{ rotate: "-42deg" }],
  },
  trackB: {
    position: "absolute",
    backgroundColor: "#7FD8FF",
    transform: [{ rotate: "33deg" }],
  },
  topSignal: {
    position: "absolute",
    backgroundColor: "#54C5FF",
    alignItems: "center",
    justifyContent: "center",
  },
  topSignalInner: {
    backgroundColor: "#ECFBFF",
  },
});
