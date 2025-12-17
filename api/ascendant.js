import swe from "swisseph";
import tzLookup from "tz-lookup";
import { DateTime } from "luxon";

const SIGNS_BG = [
  "Овен","Телец","Близнаци","Рак","Лъв","Дева",
  "Везни","Скорпион","Стрелец","Козирог","Водолей","Риби"
];

function normalizeDeg(x) {
  return ((x % 360) + 360) % 360;
}

function eclLonToSignBg(lonDeg) {
  const lon = normalizeDeg(lonDeg);
  const signIndex = Math.floor(lon / 30);
  const degInSign = lon - signIndex * 30;
  return { signBg: SIGNS_BG[signIndex], degInSign };
}

async function geocodePlace(placeText) {
  const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(placeText)}`;
  const resp = await fetch(url, {
    headers: {
      "User-Agent": "AscendantCalculator/1.0 (contact: your@email.com)"
    }
  });
  if (!resp.ok) throw new Error("Geocoding failed");
  const data = await resp.json();
  if (!data.length) throw new Error("Place not found");
  return { lat: Number(data[0].lat), lon: Number(data[0].lon) };
}

export default async function handler(req, res) {
  try {
    if (req.method !== "POST") {
      return res.status(405).json({ error: "Use POST" });
    }

    const { date, time, placeText, unknownTime } = req.body || {};
    if (!date) throw new Error("Missing date");
    if (!placeText) throw new Error("Missing place");

    const effectiveTime =
      unknownTime === true || !time ? "12:00" : time;

    const { lat, lon } = await geocodePlace(placeText);
    const tzName = tzLookup(lat, lon);

    const local = DateTime.fromISO(
      `${date}T${effectiveTime}`,
      { zone: tzName }
    );
    if (!local.isValid) throw new Error("Invalid date/time");

    const utc = local.toUTC();
    const h =
      utc.hour + utc.minute / 60 + utc.second / 3600;

    const jdUt = swe.julday(
      utc.year,
      utc.month,
      utc.day,
      h,
      swe.GREG_CAL
    );

    const [_, ascmc] = swe.houses(jdUt, lat, lon, "P");
    const ascLon = ascmc[0];

    const { signBg, degInSign } =
      eclLonToSignBg(ascLon);

    return res.json({
      ascSignBg: signBg,
      ascDegreeFormatted: `${signBg} ${degInSign.toFixed(2)}°`,
      utcIso: utc.toISO(),
      tzName,
      lat,
      lon,
      warning:
        unknownTime === true || !time
          ? "Часът е неизвестен — използван е 12:00"
          : null
    });
  } catch (e) {
    return res.status(400).json({ error: e.message });
  }
}
