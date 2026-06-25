export function isNormalScadaStatus(channel) {
  const statusCode = Number(channel?.scada_status);

  // In this project, Rapid SCADA status 1 / Defined means the channel value is valid.
  if (Number.isFinite(statusCode)) {
    return statusCode === 1;
  }

  const statusText = `${channel?.scada_status_text || ""} ${
    channel?.scada_status_description || ""
  }`.toLowerCase();

  if (
    [
      "defined",
      "channel value is defined",
      "ok",
      "normal",
      "valid",
      "good",
      "κανον",
      "έγκυρ",
      "εντάξει",
    ].some((term) => statusText.includes(term))
  ) {
    return true;
  }

  if (
    [
      "undefined",
      "invalid",
      "error",
      "alarm",
      "warning",
      "critical",
      "bad",
      "no data",
      "μη έγκυ",
      "σφάλ",
      "προειδο",
      "κρίσι",
    ].some((term) => statusText.includes(term))
  ) {
    return false;
  }

  return false;
}

export function getStatusLabel(channel) {
  return isNormalScadaStatus(channel) ? "Κανονικό" : "Μη κανονικό";
}

export function getStatusTone(channel) {
  return isNormalScadaStatus(channel) ? "normal" : "abnormal";
}