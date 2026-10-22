import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import commonEn from "../../locales/en/common.json";
import authEn from "../../locales/en/auth.json";
import rolesEn from "../../locales/en/roles.json";
import graphEn from "../../locales/en/graph.json";
import finopsEn from "../../locales/en/finops.json";

import commonSv from "../../locales/sv/common.json";
import authSv from "../../locales/sv/auth.json";
import rolesSv from "../../locales/sv/roles.json";
import graphSv from "../../locales/sv/graph.json";
import finopsSv from "../../locales/sv/finops.json";

import commonUk from "../../locales/uk/common.json";
import authUk from "../../locales/uk/auth.json";
import rolesUk from "../../locales/uk/roles.json";
import graphUk from "../../locales/uk/graph.json";
import finopsUk from "../../locales/uk/finops.json";

export const defaultNS = "common";

export const resources = {
  en: {
    common: commonEn,
    auth: authEn,
    roles: rolesEn,
    graph: graphEn,
    finops: finopsEn,
  },
  sv: {
    common: commonSv,
    auth: authSv,
    roles: rolesSv,
    graph: graphSv,
    finops: finopsSv,
  },
  uk: {
    common: commonUk,
    auth: authUk,
    roles: rolesUk,
    graph: graphUk,
    finops: finopsUk,
  },
} as const;

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources,
    lng: "sv",
    fallbackLng: "en",
    supportedLngs: ["en", "sv", "uk"],
    defaultNS,
    interpolation: {
      escapeValue: false,
    },
  });
}

export default i18n;
