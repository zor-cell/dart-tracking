import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { redirectToRememberedLanguage } from './app/core/i18n/models/language';

if (!redirectToRememberedLanguage()) {
  bootstrapApplication(AppComponent, appConfig)
    .catch((err) => console.error(err));
}
