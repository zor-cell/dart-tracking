import { ApplicationConfig, inject, LOCALE_ID, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { PrimeNG, providePrimeNG } from 'primeng/config';

import { routes } from './app.routes';
import {provideHttpClient, withInterceptors} from "@angular/common/http";
import { Noir } from "../app-theme";
import {ConfirmationService, MessageService} from "primeng/api";
import {authInterceptor, errorInterceptor} from "./core/interceptors";
import { AnnouncerService } from './features/announcement/services/announcer.service';
import { CalibrationService } from './features/calibration/services/calibration.service';
import { primeNgTranslation } from './core/config/primeng-translation';
import { SettingsService } from './features/settings/services/settings.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([errorInterceptor, authInterceptor])),
    providePrimeNG({
      theme: {
        preset: Noir
      },
    }),
    provideAppInitializer(() =>
      inject(PrimeNG).setTranslation(primeNgTranslation(inject(LOCALE_ID))),
    ),
    MessageService,
    ConfirmationService,
    // Listens from app start, so an announcer_state sent on join is never missed.
    provideAppInitializer(() => void inject(AnnouncerService)),
    provideAppInitializer(() => void inject(CalibrationService)),
    // Loads the account's settings from app start, so its language is followed after sign-in too.
    provideAppInitializer(() => void inject(SettingsService)),
  ]
};
