import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { ApiService } from '../services/api.service';
import { map, catchError, of } from 'rxjs';

export const authGuard: CanActivateFn = (route, state) => {
  const api = inject(ApiService);
  const router = inject(Router);

  if (!api.isLoggedIn()) {
    router.navigate(['/login']);
    return false;
  }

  // Check admin requirement
  const requiresAdmin = route.data?.['requiresAdmin'] === true;

  return api.getMe().pipe(
    map(res => {
      if (res.status === 'success') {
        if (requiresAdmin && res.user.role !== 'admin') {
          router.navigate(['/dashboard']);
          return false;
        }
        return true;
      }
      api.logout();
      router.navigate(['/login']);
      return false;
    }),
    catchError(() => {
      api.logout();
      router.navigate(['/login']);
      return of(false);
    })
  );
};
