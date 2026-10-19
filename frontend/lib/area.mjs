/** Thai land units, rounded to 0.01 square wah; not a cadastral survey. */
export function thaiLandArea(areaM2){
 if(typeof areaM2!=='number'||!Number.isFinite(areaM2)||areaM2<0)throw new RangeError('Nonnegative finite area required');
 const hundredths=Math.round(areaM2*25);
 if(!Number.isSafeInteger(hundredths))throw new RangeError('Area exceeds display precision');
 return {rai:Math.floor(hundredths/40000),ngan:Math.floor((hundredths%40000)/10000),squareWah:(hundredths%10000)/100};
}
