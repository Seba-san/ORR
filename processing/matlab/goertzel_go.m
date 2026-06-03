%% Sincronización para Demodulador AFSK con Goertzel
% Basado en el código proporcionado, extrae los parámetros y añade
% una rutina de sincronización que encuentra el offset óptimo de muestras
% para alinear los bloques de símbolos.
% Compatible con MATLAB R2018a (funciones locales al final)

clear; close all; clc;

% 1. Extracción de configuración del sistema original
% load('bits_enviados.mat')
alpha=1;
fs_target = 12288;      % Frecuencia de muestreo objetivo (Hz)
N = 48*alpha;                % Tamaño del bloque de muestras (símbolo)
f1 = 768;                % Frecuencia inferior (Hz) - Espacio / 0
f2 = 1280;               % Frecuencia superior (Hz) - Marca / 1
f_noise = 1024;          % Frecuencia intermedia para estimación de ruido (Hz)
umbral_snr = 4.0;        % Factor multiplicador sobre el piso de ruido

% 2. Lectura y acondicionamiento del audio
file='dataset_grab_micro_camara.wav';
file='grabacion_2.wav';
% audioread('grabacion_2.wav');
try
    [grabAudio, fs_orig] = audioread(file);
catch
    error(['No se pudo leer el archivo ' file '. Verifique el directorio.']);
end

% Conversión a mono si es estéreo
if size(grabAudio, 2) > 1
    grabAudio = mean(grabAudio, 2);
end

% Remuestreo estricto a fs_target
audio_resampled = resample(grabAudio, fs_target, fs_orig);
% 2.1 Filtro pasabanda 300 Hz - 3000 Hz
% Diseño de filtro Butterworth de orden 4 con respuesta de fase cero
Wn = [300 3000] / (fs_target/2);  % Frecuencias normalizadas
[b, a] = butter(4, Wn, 'bandpass');
audio_filtered = filtfilt(b, a, audio_resampled);
audio_resampled=audio_filtered;
% Se quita el primer bloque por ruido
% audio_resampled=audio_resampled(N/4:end);
plot(audio_resampled)
%%
clear; close all; clc;

% 1. Extracción de configuración del sistema original
load('dataset_real.mat')
alpha=1;
fs_target = 12288;      % Frecuencia de muestreo objetivo (Hz)
% N = 48*alpha;                % Tamaño del bloque de muestras (símbolo)
N = 2*150*24 ; % Data 4 con  N = 5*24, data 256 con N=7200=300*24
%data 128 con N=1*150*24
% N=384;
N= round(6950/2^7)%256: 6950 % dataset_real
f1 = 676;% Valor obtenido para el dataset_real %768;                % Frecuencia inferior (Hz) - Espacio / 0
f2 = 1203;% Valor obtenido para el dataset_real   %1280     % Frecuencia superior (Hz) - Marca / 1
f_noise = 1024;  
audio_resampled=data2;
bits_tx=[1,0,1,0,1,1,0,0,1,1,1,0,0,0,1,1,0,0,1,0,1,0];
L=size(audio_resampled,1);
audio_resampled=[audio_resampled(1)*ones(round(L),1)' audio_resampled' audio_resampled(end)*ones(round(L/2),1)']';

plot(audio_resampled)
%% Sincronizacion gruesa
% 3. Parámetros precomputados de Goertzel
k1 = round(N * f1 / fs_target);
k2 = round(N * f2 / fs_target);
k_noise = round(N * f_noise / fs_target);

coeff1 = 2 * cos(2 * pi * k1 / N);
coeff2 = 2 * cos(2 * pi * k2 / N);
coeff_noise = 2 * cos(2 * pi * k_noise / N);


% 5. Sincronización: encontrar el offset óptimo de muestras
num_blocks_total = floor(length(audio_resampled) / N);
% BUsqueda de potencia promedio
potNoise=zeros(1,num_blocks_total);
pot1=zeros(1,num_blocks_total);
pot2=zeros(1,num_blocks_total);
potSignal=zeros(1,num_blocks_total);
for b = 1:num_blocks_total
    bloque = audio_resampled((b-1)*N + 1 : b*N);
    potSignal(b)=sum(bloque.^2)./size(bloque,1);
    potNoise(b)=goertzel_mag(bloque,coeff_noise);
    [~,pot1(b)]=goertzel_mag(bloque,coeff1);
    [~,pot2(b)]=goertzel_mag(bloque,coeff2);
end
potPromNoise=[median(potNoise),std(potNoise)];

% potProm1=[minStd(pot1),std(pot1)];
% potProm2=[minStd(pot2),std(pot2)];
% potSignal=movmean(potSignal,10);
potTot=potSignal;% Por si tiene un offset
potToth=minStd(potTot);
idx=find(potTot>potToth,5);
idx_=idx(idx>5);

% Asume que la potencia aumenta cuando aparece la señal y que ademas es la
% mayor potencia. Luego el cumsum genera una curva en forma de s que se
% puede aproximar por 3 rectas. Se arma la recta del medio y se calcula la
% interseccion con el eje x de esa recta. Luego ese indice es el mas
% proximo al inicio.
cpTot=cumsum(potTot);
p10=(max(cpTot)-min(cpTot))*0.1+min(cpTot); % ojo aca, para mayor robustez se toma el 20%
p90=(max(cpTot)-min(cpTot))*0.9+min(cpTot);
[~,i10]=min(abs(cpTot-p10));
[~,i90]=min(abs(cpTot-p90));
a=(p90-p10)/(i90-i10);
y0=median(cpTot(1:i10));
b=p10-a*i10;
x0=round((y0-b)/a);
x0=idx_(1);
figure(2)
plot(cpTot,'.b');hold on
plot(x0,cpTot(x0),'xr');
plot(1:i90,a*(1:i90)+b,'-g')
hold off

%
% plot(potTot,'.b'); hold on
% plot(1:num_blocks_total,potToth*ones(1,num_blocks_total),'-r');hold off
%

% primer_bloque_valido=round((x0*N-1)/N+1);
primer_bloque_valido=x0;
b=primer_bloque_valido;
potSignal=[minStd(pot1+pot2),std(pot1+pot2)];
% figure(3)
% plot(pot1,'.b');hold on
% plot(1:size(pot1,2),potProm1(1)*ones(size(pot1,2),1), '.r');hold off
% title('señal f1')
% figure(4)
% plot(pot2,'.b');hold on
% plot(1:size(pot2,2),potProm2(1)*ones(size(pot2,2),1), '.r');hold off
% title('señal f2')
%figure(5)
%plot(pot1+pot2,'.b');hold on
%plot(1:size(pot1,2),potSignal(1)*ones(size(pot1,2),1), '.r');hold off
%title('señal f1+f2')
%
% 
% 5.1 Primero, detectar el primer bloque con señal usando el offset por defecto (0)
%{
primer_bloque_valido = -1;
for b = 2:num_blocks_total % No mira el primer bloque ya que suele ser ruido
    bloque = audio_resampled((b-1)*N + 1 : b*N);
    [~,mag1]=goertzel_mag(bloque, coeff1);
    [~,mag2]=goertzel_mag(bloque, coeff2);
    mag_noise=goertzel_mag(bloque, coeff_noise);
    
%     [mag1, mag2, mag_noise] = calc_mags(bloque);
    if (mag1+mag2 > potSignal(1))
        primer_bloque_valido = b;
        break;
    end
end
primer_bloque_valido
%}
%
figure(1)
plot(audio_resampled);hold on
plot((b-1)*N + 1 : b*N,audio_resampled((b-1)*N + 1 : b*N),'-r');hold off
%% Sincronizacion fina

% %{ 
if primer_bloque_valido == -1
    error('No se detectó ninguna señal válida en el archivo.');
end

% Muestra de inicio aproximada (usando offset 0)
inicio_aproximado = (primer_bloque_valido - 1) * N + 1;

% 5.2 Búsqueda fina alrededor del inicio aproximado
% Rango de búsqueda: desde -N/2 hasta +N/2 alrededor del inicio_aproximado
rango_busqueda = -round(2*N) : round(2*N);
rango_busqueda = rango_busqueda + inicio_aproximado;
% Limitar a índices válidos (1 ... length(audio_resampled)-N+1)
rango_busqueda = rango_busqueda(rango_busqueda >= 1 & rango_busqueda <= length(audio_resampled)-N+1);

mejor_offset = inicio_aproximado;
mejor_energia = 0;
energia=0;
energiaV=[];
potSignal2=zeros(1,size(rango_busqueda,2));
% Evaluar cada offset candidato
for idx = rango_busqueda
    % Tomar el primer bloque a partir de este offset
    bloque = audio_resampled(idx : idx+N-1);
    [~,mag1]=goertzel_mag(bloque, coeff1);
    [~,mag2]=goertzel_mag(bloque, coeff2);
%     [mag1, mag2, ~] = calc_mags(bloque);
potSignal2(idx-rango_busqueda(1)+1)=sum(bloque.^2)./size(bloque,1);
    
    % Usar la suma de magnitudes como métrica (podría ser max, o suma)
%     energiaV(end+1) = max(mag1, mag2);
    energiaV(end+1) = mag1 + mag2;
%     plot(idx,energia,'.b');hold on
   
%     if energia > mejor_energia
%         mejor_energia = energia;
%         mejor_offset = idx;
%     end
%{
figure(1)
plot(rango_busqueda,audio_resampled(rango_busqueda),'-b');hold on
plot(idx : idx+N-1,audio_resampled(idx : idx+N-1),'.r');hold off
figure(2)
plot(idx-rango_busqueda(1)+1,potSignal2(idx-rango_busqueda(1)+1),'.b');hold on
pause(0.2)
%}
end
% 5.3: La energia sube rapidamente y luego se aplana, por esto se calculan
% las diferencias y como es ruidoso, se toma una media movil. Luego se toma
% la mitad del rango entre el maximo valor de la media movil y el minimo.
% derivadaMedia=movmean(diff(energiaV),N);
% medio=(max(derivadaMedia)-min(derivadaMedia))/2;
% [~,b]=min(abs(derivadaMedia-medio));
% [~,b]=max(energiaV);
% cpTot=cumsum(energiaV);
cpTot=potSignal2;
p10=(max(cpTot)-min(cpTot))*0.2+min(cpTot); % ojo aca, para mayor robustez se toma el 20%
p90=(max(cpTot)-min(cpTot))*0.8+min(cpTot);
[~,i10]=min(abs(cpTot-p10));
[~,i90]=min(abs(cpTot-p90));
a=(p90-p10)/(i90-i10);
y0=mean(cpTot(1:i10));
% x0=round(-p10/a + i10+y0/a);
x0=round(-p10/a + i10+y0/a)+N;
figure(2)
plot(cpTot,'.b');hold on
plot(x0,cpTot(x0),'xr');hold off
mejor_offset=x0+rango_busqueda(1);

fprintf('Offset óptimo encontrado: muestra %d\n', mejor_offset);
%}
% mejor_offset=(b-1)*N + 1 ;
figure(3)
plot(audio_resampled);hold on
plot(mejor_offset,audio_resampled(mejor_offset),'or');hold off
%%
k=round(N/100);
kernel = zeros(1, k+1);
kernel(1) = 1;
kernel(k+1) = -1;

% Aplicación del filtro
dy = filter(kernel, 1, cpTot);
th=max(abs(dy))*0.1;
dy=abs(dy);
idx=find(dy>th,5);
idx_=idx(idx>5);
x0=idx_(1)+N;

% dy = filter(kernel, 1, abs(dy));
% [~,x0]=max(dy);

% plot(dy,'.')
mejor_offset=x0+rango_busqueda(1);
figure(4)
plot(audio_resampled);hold on
plot(mejor_offset,audio_resampled(mejor_offset),'or');hold off

%% Obtiene el nuevo umbral de potencia con señal sincronizada
num_blocks_sinc = floor((length(audio_resampled) - mejor_offset + 1) / N);
% trama_recibida = -ones(1, num_blocks_sinc);
% umbral=-100;
potSignal=zeros(1,num_blocks_sinc);
mag1=zeros(1,num_blocks_sinc);
mag2=zeros(1,num_blocks_sinc);
for b = 1:num_blocks_sinc
    inicio = mejor_offset + (b-1)*N;
    bloque = audio_resampled(inicio : inicio+N-1);
    potSignal(b)=sum(bloque.^2)./N;
    [~,mag1(b)]=goertzel_mag(bloque, coeff1);
    [~,mag2(b)]=goertzel_mag(bloque, coeff2);
end
umbral=minStd(potSignal);
figure(1)
plot(potSignal,'.b');hold on
plot(1:num_blocks_sinc,umbral*ones(1,num_blocks_sinc),'.r');hold off



%% 6. Demodulación completa usando el offset sincronizado
% Ajustar el inicio para que el primer bloque comience en 'mejor_offset'
% Nota: puede que el offset no sea múltiplo de N, así que procesamos desde allí
% hasta el final, ignorando las muestras iniciales no alineadas.

% Calcular cuántos bloques completos caben desde mejor_offset
num_blocks_sinc = floor((length(audio_resampled) - mejor_offset + 1) / N);
trama_recibida = -ones(1, num_blocks_sinc);

for b = 1:num_blocks_sinc
    inicio = mejor_offset + (b-1)*N;
    bloque = audio_resampled(inicio : inicio+N-1);
    potSignal=sum(bloque.^2)./N;

    
    [~,mag1]=goertzel_mag(bloque, coeff1);
    [~,mag2]=goertzel_mag(bloque, coeff2);
    [~,mag_noise]=goertzel_mag(bloque, coeff_noise);
    
    % Decisión con umbral de ruido
%     if mag_noise<potPromNoise(1)+potPromNoise(2)
%          if (mag2 >  mag1 ) && (log(mag2/ potSignal_) >umbral)
%              if (mag2 > potProm2(1) && mag1 < potProm1(1) )
        if (mag2 >  mag1 ) &&  potSignal >umbral
              trama_recibida(b) = 0;
        elseif (mag1 >  mag2 ) &&  potSignal >umbral
             trama_recibida(b) = 1;               
         else             
             trama_recibida(b) = -1; % ruido o silencio 
%              -1
         end
%     else
%         trama_recibida(b) = -1; % ruido o silencio
             
%     end
%
%{
if inicio+2*N-1<size(audio_resampled,1)
figure(1)
plot(inicio-2*N : inicio+N*2-1,audio_resampled(inicio-2*N : inicio+2*N-1),'-b');hold on
% plot(audio_resampled,'-b');hold on
plot(inicio : inicio+N-1,audio_resampled(inicio : inicio+N-1),'-r');hold off
 trama_recibida(b)
 ylim([min(audio_resampled) max(audio_resampled)])
%  pause()
end
%}
end

primer_valido = find(trama_recibida ~= -1, 1, 'first');
if isempty(primer_valido)
    error('No se encontraron datos válidos en la trama.');
end
trama_recibida = trama_recibida(primer_valido:end);

% Mostrar resultado
% disp('Trama demodulada (bits y -1 para ruido):');
% disp(trama_recibida);
disp('Procesamiento terminado');
%
disp('Trama demodulada resultante:');
% load('bits_enviados.mat')
Ntrama=size(bits_tx,2);
error=0;
incertidumbre=0;
for i=1:Ntrama
    if trama_recibida(i)~=bits_tx(i)
        if trama_recibida(i)==-1
            incertidumbre=incertidumbre+1;
        else
        error=error+1;
        end
    end
end
disp(['Cantidad de datos sin errores: '  num2str(Ntrama-error-incertidumbre) ])
disp(['Cantidad de errores detectados: '  num2str(error) ])
disp(['Cantidad de datos con dudas: ' num2str(incertidumbre)])
disp(['cantidad de datos transmitidos: ' num2str(Ntrama)])
[trama_recibida(1:Ntrama)',bits_tx']
% '
% disp(trama_recibida(1:Ntrama)',bits_tx');

%% Función local de Goertzel (debe ir al final del script)
function [mag,magN] = goertzel_mag(bloque, coeff)
    % Implementación del filtro Goertzel para una frecuencia
    Q1 = 0; Q2 = 0;
    N = length(bloque);
    for i = 1:N
        Q0 = coeff * Q1 - Q2 + bloque(i);
        Q2 = Q1;
        Q1 = Q0;
    end
    mag = Q1^2 + Q2^2 - Q1 * Q2 * coeff;
    magN=2*mag/N^2;
end


function T = kmeans1d(data)
    c_low = min(data); c_high = max(data); T_old = inf;
    for i = 1:50
        T = (c_low + c_high)/2;
        left = data(data<T); right = data(data>=T);
        if isempty(left), c_low = min(data); else c_low = mean(left); end
        if isempty(right), c_high = max(data); else c_high = mean(right); end
        if abs(T - T_old) < 1e-6, break; end
        T_old = T;
    end
end

function T=minStd(data)
N=50;
for i=1:N
    mi=min(data);
    ma=max(data);
    T=(ma-mi)/2+mi;
    
    figure(1)
    plot(data,'.b');hold on
    plot(1:length(data),T*ones(1,length(data)),'.g');hold off
    
    di=data(data<T);
    da=data(data>T);
    
    if std(di)*2<std(da)
        break
    else
        if std(da)==0
           break
        end
        data=di;
    end
end
end

% function T=kmeans1d(data)
% c_low = min(data); c_high = max(data);
% for i=1:10
%     T = (c_low + c_high)/2;
%     c_low = mean(data(data<T));
%     c_high = mean(data(data>=T)); 
% end
% end