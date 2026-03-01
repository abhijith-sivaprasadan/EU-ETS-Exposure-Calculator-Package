import { Module } from '@nestjs/common';
import { EtsModule } from './ets/ets.module';

@Module({
  imports: [EtsModule],
})
export class AppModule {}
